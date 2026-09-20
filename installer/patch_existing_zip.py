#!/usr/bin/env python3
#
# Patch an existing Lunaris AOSP OTA zip to add interactive hardware frequency selection
# (Display 120/130Hz & GPU 675/692MHz).
#

import sys
import os
import zipfile
import tempfile
import shutil
import subprocess

def patch_ota_zip(input_zip_path, output_zip_path=None):
    if not os.path.exists(input_zip_path):
        print(f"Error: {input_zip_path} not found.")
        sys.exit(1)

    top_dir = os.environ.get("ANDROID_BUILD_TOP", os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))
    vayu_prebuilt = os.path.join(top_dir, "device/xiaomi/vayu/prebuilt")
    script_sh = os.path.join(top_dir, "device/xiaomi/sm8150-common/installer/lunaris_config.sh")
    dtbo_120 = os.path.join(vayu_prebuilt, "dtbo_120.img")
    dtbo_130 = os.path.join(vayu_prebuilt, "dtbo_130.img")
    boot_675 = os.path.join(vayu_prebuilt, "boot_675.img")

    if not os.path.exists(script_sh) or not os.path.exists(dtbo_120) or not os.path.exists(dtbo_130):
        print(f"Error: Missing prerequisite files in repository: {script_sh}, {dtbo_120}, {dtbo_130}")
        sys.exit(1)

    if output_zip_path is None:
        base, ext = os.path.splitext(input_zip_path)
        output_zip_path = f"{base}-interactive{ext}"

    print(f"[*] Reading source package: {input_zip_path}")
    print(f"[*] Target package: {output_zip_path}")

    # Read updater-script from source zip
    with zipfile.ZipFile(input_zip_path, "r") as in_zip:
        updater_script = in_zip.read("META-INF/com/google/android/updater-script").decode("utf-8")

    # 1. Inject FullOTA_InstallBegin right after the ASCII banner
    begin_hook = """
# --- Lunaris Hardware Selector (Interactive Begin) ---
package_extract_dir("lunaris", "/tmp/lunaris");
set_metadata_recursive("/tmp/lunaris", "uid", 0, "gid", 0, "dmode", 0755, "fmode", 0755);
run_program("/tmp/lunaris/lunaris_config.sh");
# -----------------------------------------------------
"""
    # Insert right after the header ui_print block (after "Manufacturer : Xiaomi")
    marker = 'ui_print("***********************************************");\nui_print("                                         ");'
    if marker in updater_script:
        updater_script = updater_script.replace(marker, marker + "\n" + begin_hook, 1)
    else:
        # Fallback: insert before package_extract_dir("install"
        updater_script = updater_script.replace('package_extract_dir("install"', begin_hook + '\npackage_extract_dir("install"', 1)

    # 2. Inject FullOTA_InstallEnd replacing single dtbo write
    end_hook = """
# --- Lunaris Hardware Selection Apply ---
ifelse(file_getprop("/tmp/lunaris_choice.prop", "display_hz") == "130",
  (
    ui_print(">> Flashing Overclocked 130Hz DTBO...");
    package_extract_file("dtbo_130.img", "/dev/block/bootdevice/by-name/dtbo");
  ),
  (
    ui_print(">> Flashing Stock 120Hz DTBO...");
    package_extract_file("dtbo_120.img", "/dev/block/bootdevice/by-name/dtbo");
  )
);
ifelse(file_getprop("/tmp/lunaris_choice.prop", "gpu_clock") == "675",
  (
    ui_print(">> Flashing Stock 675MHz GPU Boot Image...");
    package_extract_file("boot_675.img", "/dev/block/bootdevice/by-name/boot");
  ),
  (
    ui_print(">> Keeping Overclocked 692MHz GPU Boot Image...");
  )
);
delete_recursive("/tmp/lunaris");
delete("/tmp/lunaris_choice.prop");
# ----------------------------------------
"""
    old_dtbo = 'package_extract_file("dtbo.img", "/dev/block/bootdevice/by-name/dtbo");'
    if old_dtbo in updater_script:
        updater_script = updater_script.replace(old_dtbo, end_hook)
    else:
        print("Warning: could not find old dtbo write line in updater-script, appending hook to end.")
        updater_script += "\n" + end_hook

    # 3. Create updated zip
    print("[*] Creating patched OTA zip...")
    with zipfile.ZipFile(input_zip_path, "r") as in_zip:
        with zipfile.ZipFile(output_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as out_zip:
            for item in in_zip.infolist():
                if item.filename == "META-INF/com/google/android/updater-script":
                    out_zip.writestr(item, updater_script.encode("utf-8"))
                else:
                    data = in_zip.read(item.filename)
                    out_zip.writestr(item, data)

            # Add new files
            print("[*] Adding lunaris_config.sh...")
            with open(script_sh, "rb") as f:
                out_zip.writestr("lunaris/lunaris_config.sh", f.read())

            print("[*] Adding dtbo_120.img & dtbo_130.img...")
            with open(dtbo_120, "rb") as f:
                out_zip.writestr("dtbo_120.img", f.read())
            with open(dtbo_130, "rb") as f:
                out_zip.writestr("dtbo_130.img", f.read())

            if os.path.exists(boot_675):
                print("[*] Adding boot_675.img...")
                with open(boot_675, "rb") as f:
                    out_zip.writestr("boot_675.img", f.read())

    print(f"[+] Successfully created patched OTA package:\n    {output_zip_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: patch_existing_zip.py <input.zip> [output.zip]")
        sys.exit(1)
    out = sys.argv[2] if len(sys.argv) > 2 else None
    patch_ota_zip(sys.argv[1], out)
