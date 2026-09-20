# Copyright (C) 2009 The Android Open Source Project
# Copyright (c) 2011, The Linux Foundation. All rights reserved.
# Copyright (C) 2017-2018 The LineageOS Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import tempfile
import importlib.util
import common

LUNARIS_CONFIG_SCRIPT = r"""#!/sbin/sh
#
# Lunaris AOSP Hardware Frequency Selector for Poco X3 Pro (vayu)
# Runs during recovery installation to configure Display (120/130Hz) and GPU (675/692MHz).
#

CHOICE_PROP="/tmp/lunaris_choice.prop"

# Pre-populate default properties immediately so file_getprop never encounters a missing file
mkdir -p "$(dirname "$CHOICE_PROP")"
echo "display_hz=120" > "$CHOICE_PROP"
echo "gpu_clock=675" >> "$CHOICE_PROP"

# Auto-detect Recovery command pipe for ui_print
OUTFD=
if [ -r "/proc/$PPID/cmdline" ]; then
    PARENT_FD=$(tr '\0' '\n' < "/proc/$PPID/cmdline" 2>/dev/null | sed -n '3p')
    if [ -n "$PARENT_FD" ] && [ -e "/proc/$$/fd/$PARENT_FD" ]; then
        OUTFD="/proc/$$/fd/$PARENT_FD"
    fi
fi

if [ -z "$OUTFD" ]; then
    for fd in 3 4 5 6 7 8; do
        if [ -e "/proc/$$/fd/$fd" ]; then
            link=$(readlink "/proc/$$/fd/$fd" 2>/dev/null)
            case "$link" in
                pipe:*)
                    OUTFD="/proc/$$/fd/$fd"
                    break
                    ;;
            esac
        fi
    done
fi

if [ -z "$OUTFD" ] && [ -n "$PPID" ] && [ -d "/proc/$PPID/fd" ]; then
    for fd in 3 4 5 6 7 8; do
        if [ -e "/proc/$PPID/fd/$fd" ]; then
            link=$(readlink "/proc/$PPID/fd/$fd" 2>/dev/null)
            case "$link" in
                pipe:*)
                    OUTFD="/proc/$PPID/fd/$fd"
                    break
                    ;;
            esac
        fi
    done
fi

ui_print() {
    if [ -n "$OUTFD" ]; then
        echo "ui_print $1" > "$OUTFD" 2>/dev/null
    fi
    # Also log to stdout for recovery.log
    echo "$1"
}

KEY_CHOICE=""

wait_key_selection() {
    local default_val="$1"
    local opt_plus="$2"
    local opt_minus="$3"
    local timeout_sec=10
    local key_file="/tmp/lunaris_key"

    rm -f "$key_file"
    KEY_CHOICE="$default_val"

    # Start background key event listener
    (
        getevent -l 2>/dev/null | while read -r line; do
            case "$line" in
                *KEY_VOLUMEUP*DOWN*|*KEY_VOLUMEUP*down*|*0073*00000001*|*0073*1*)
                    echo "$opt_plus" > "$key_file"
                    exit 0
                    ;;
                *KEY_VOLUMEDOWN*DOWN*|*KEY_VOLUMEDOWN*down*|*0072*00000001*|*0072*1*)
                    echo "$opt_minus" > "$key_file"
                    exit 0
                    ;;
            esac
        done
    ) &
    local listener_pid=$!

    local elapsed=0
    while [ $elapsed -lt $timeout_sec ]; do
        if [ -s "$key_file" ]; then
            KEY_CHOICE=$(tr -d ' \t\r\n' < "$key_file")
            break
        fi
        sleep 1
        elapsed=$((elapsed + 1))
        local remaining=$((timeout_sec - elapsed))
        if [ $remaining -gt 0 ] && [ $((remaining % 3)) -eq 0 ]; then
            ui_print "  ... remaining: ${remaining}s"
        fi
    done

    kill -9 $listener_pid 2>/dev/null
    killall getevent 2>/dev/null
    rm -f "$key_file"
}

# --- Main Selector Interface ---

ui_print " "
ui_print "==============================================="
ui_print "       Installing step: 1/2"
ui_print "       Lunaris AOSP Display & GPU Selector"
ui_print "==============================================="
ui_print " "

# Step 1: Display Refresh Rate
ui_print "[1/2] Display Refresh Rate:"
ui_print "  [VOLUME +] Stock 120Hz"
ui_print "  [VOLUME -] Overclocked 130Hz"
ui_print "  (Timeout 10 sec -> Stock 120Hz)"

wait_key_selection "120" "120" "130"
DISP_CHOICE="$KEY_CHOICE"

if [ "$DISP_CHOICE" = "130" ]; then
    ui_print ">> Selected: [Overclocked 130Hz]"
else
    ui_print ">> Selected: [Stock 120Hz]"
    DISP_CHOICE="120"
fi

ui_print " "

# Step 2: GPU Clock
ui_print "[2/2] Max GPU Frequency:"
ui_print "  [VOLUME +] Stock GPU (675MHz)"
ui_print "  [VOLUME -] Overclocked GPU (692MHz)"
ui_print "  (Timeout 10 sec -> Stock GPU (675MHz))"

wait_key_selection "675" "675" "692"
GPU_CHOICE="$KEY_CHOICE"

if [ "$GPU_CHOICE" = "692" ]; then
    ui_print ">> Selected: [Overclocked GPU (692MHz)]"
else
    ui_print ">> Selected: [Stock GPU (675MHz)]"
    GPU_CHOICE="675"
fi

ui_print " "
ui_print "==============================================="
ui_print " Config saved:"
ui_print "  - Display : ${DISP_CHOICE} Hz"
ui_print "  - GPU     : ${GPU_CHOICE} MHz"
ui_print " Starting installation step 2/2..."
ui_print "==============================================="
ui_print " "

# Save finalized properties to /tmp/lunaris_choice.prop
echo "display_hz=${DISP_CHOICE}" > "$CHOICE_PROP"
echo "gpu_clock=${GPU_CHOICE}" >> "$CHOICE_PROP"

exit 0
"""

def GetTopDir(info=None):
  top = os.environ.get("ANDROID_BUILD_TOP")
  if top and os.path.isdir(os.path.join(top, "device", "xiaomi", "sm8150-common")):
    return top

  cwd = os.getcwd()
  if os.path.isdir(os.path.join(cwd, "device", "xiaomi", "sm8150-common")):
    return cwd

  if info and hasattr(info, "info_dict") and info.info_dict:
    tool_ext = info.info_dict.get("tool_extensions")
    if tool_ext:
      cand = os.path.abspath(os.path.join(cwd, tool_ext, "..", "..", ".."))
      if os.path.isdir(os.path.join(cand, "device", "xiaomi", "sm8150-common")):
        return cand

  cand = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
  if os.path.isdir(os.path.join(cand, "device", "xiaomi", "sm8150-common")):
    return cand

  if os.path.isdir("/home/Ximi/Poco-X3-Pro-Lunaris-AOSP"):
    return "/home/Ximi/Poco-X3-Pro-Lunaris-AOSP"

  return None

def FullOTA_InstallBegin(info):
  OTA_InstallBegin(info)
  return

def IncrementalOTA_InstallBegin(info):
  OTA_InstallBegin(info)
  return

def FullOTA_InstallEnd(info):
  OTA_InstallEnd(info)
  return

def IncrementalOTA_InstallEnd(info):
  OTA_InstallEnd(info)
  return

def AddImage(info, basename, dest):
  path = "IMAGES/" + basename
  if path not in info.input_zip.namelist():
    return

  data = info.input_zip.read(path)
  common.ZipWriteStr(info.output_zip, basename, data)
  info.script.AppendExtra('package_extract_file("%s", "%s");' % (basename, dest))

def AddFileToZip(info, src_path, dest_name):
  if src_path and os.path.exists(src_path):
    common.ZipWrite(info.output_zip, src_path, arcname=dest_name)
    return True
  return False

def OTA_InstallBegin(info):
  top_dir = GetTopDir(info)
  script_data = None

  if top_dir:
    script_path = os.path.join(top_dir, "device", "xiaomi", "sm8150-common", "installer", "lunaris_config.sh")
    if os.path.exists(script_path):
      try:
        with open(script_path, "r", encoding="utf-8") as f:
          script_data = f.read()
      except Exception:
        pass

  if not script_data:
    script_data = LUNARIS_CONFIG_SCRIPT

  common.ZipWriteStr(info.output_zip, "lunaris/lunaris_config.sh", script_data)
  info.script.AppendExtra('package_extract_dir("lunaris", "/tmp/lunaris");')
  info.script.AppendExtra('set_metadata_recursive("/tmp/lunaris", "uid", 0, "gid", 0, "dmode", 0755, "fmode", 0755);')
  info.script.AppendExtra('run_program("/tmp/lunaris/lunaris_config.sh");')
  return

def OTA_InstallEnd(info):
  info.script.Print("Patching firmware & hardware configuration...")

  top_dir = GetTopDir(info)
  vayu_prebuilt = None
  if top_dir:
    vayu_prebuilt = os.path.join(top_dir, "device", "xiaomi", "vayu", "prebuilt")

  dtbo_120 = os.path.join(vayu_prebuilt, "dtbo_120.img") if vayu_prebuilt else None
  dtbo_130 = os.path.join(vayu_prebuilt, "dtbo_130.img") if vayu_prebuilt else None
  boot_675_prebuilt = os.path.join(vayu_prebuilt, "boot_675.img") if vayu_prebuilt else None

  has_vayu_selector = dtbo_120 and dtbo_130 and os.path.exists(dtbo_120) and os.path.exists(dtbo_130)

  if has_vayu_selector:
    # 1. Package both DTBO options
    print("Lunaris AOSP: Packaging 120Hz and 130Hz DTBO images into OTA package...")
    AddFileToZip(info, dtbo_120, "dtbo_120.img")
    AddFileToZip(info, dtbo_130, "dtbo_130.img")

    # 2. Package stock 675MHz boot image
    has_boot_675 = False

    # Attempt dynamic generation from current build's IMAGES/boot.img
    if "IMAGES/boot.img" in info.input_zip.namelist() and top_dir:
      try:
        mod_path = os.path.join(top_dir, "device", "xiaomi", "sm8150-common", "installer", "generate_boot_675.py")
        if os.path.exists(mod_path):
          print("Lunaris AOSP: Generating dynamic 675MHz GPU boot image from IMAGES/boot.img...")
          spec = importlib.util.spec_from_file_location("generate_boot_675", mod_path)
          gen_mod = importlib.util.module_from_spec(spec)
          spec.loader.exec_module(gen_mod)

          with tempfile.TemporaryDirectory(prefix="ota_boot_") as tmp_ota:
            src_boot = os.path.join(tmp_ota, "boot.img")
            dst_boot = os.path.join(tmp_ota, "boot_675.img")
            with open(src_boot, "wb") as f:
              f.write(info.input_zip.read("IMAGES/boot.img"))
            gen_mod.generate_boot_675(src_boot, dst_boot, top_dir=top_dir)
            if os.path.exists(dst_boot) and os.path.getsize(dst_boot) > 0:
              AddFileToZip(info, dst_boot, "boot_675.img")
              has_boot_675 = True
              print("Lunaris AOSP: Successfully generated and added dynamic boot_675.img")
      except Exception as e:
        print("Notice: Dynamic boot_675 generation skipped: %s" % e)

    # Fallback to prebuilt boot_675.img
    if not has_boot_675 and boot_675_prebuilt and os.path.exists(boot_675_prebuilt):
      print("Lunaris AOSP: Using prebuilt boot_675.img fallback...")
      AddFileToZip(info, boot_675_prebuilt, "boot_675.img")
      has_boot_675 = True

    # 3. Flashing DTBO based on user choice in Recovery
    info.script.AppendExtra("""ifelse(file_getprop("/tmp/lunaris_choice.prop", "display_hz") == "130",
  (
    ui_print(">> Flashing Overclocked 130Hz DTBO...");
    package_extract_file("dtbo_130.img", "/dev/block/bootdevice/by-name/dtbo");
  ),
  (
    ui_print(">> Flashing Stock 120Hz DTBO...");
    package_extract_file("dtbo_120.img", "/dev/block/bootdevice/by-name/dtbo");
  )
);""")

    # 4. Flashing Boot image based on user choice in Recovery
    # Note: boot.img (692MHz) was already flashed during WriteRawImage.
    # If user selected 675MHz stock, we flash boot_675.img over /boot.
    if has_boot_675:
      info.script.AppendExtra("""ifelse(file_getprop("/tmp/lunaris_choice.prop", "gpu_clock") == "675",
  (
    ui_print(">> Flashing Stock 675MHz GPU Boot Image...");
    package_extract_file("boot_675.img", "/dev/block/bootdevice/by-name/boot");
  ),
  (
    ui_print(">> Keeping Overclocked 692MHz GPU Boot Image...");
  )
);""")

    # 5. Cleanup temporary selector files
    info.script.AppendExtra('delete_recursive("/tmp/lunaris");')
    info.script.AppendExtra('delete("/tmp/lunaris_choice.prop");')
  else:
    AddImage(info, "dtbo.img", "/dev/block/bootdevice/by-name/dtbo")

  AddImage(info, "vbmeta.img", "/dev/block/by-name/vbmeta")
  AddImage(info, "vbmeta_system.img", "/dev/block/bootdevice/by-name/vbmeta_system")
  return
