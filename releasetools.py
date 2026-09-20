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
import common
import re

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
  if os.path.exists(src_path):
    with open(src_path, "rb") as f:
      data = f.read()
    common.ZipWriteStr(info.output_zip, dest_name, data)
    return True
  return False

def OTA_InstallBegin(info):
  # Check for interactive hardware selector script
  script_path = os.path.join(os.path.dirname(__file__), "installer", "lunaris_config.sh")
  if os.path.exists(script_path):
    with open(script_path, "r") as f:
      script_data = f.read()
    common.ZipWriteStr(info.output_zip, "lunaris/lunaris_config.sh", script_data)
    info.script.AppendExtra('package_extract_dir("lunaris", "/tmp/lunaris");')
    info.script.AppendExtra('set_metadata_recursive("/tmp/lunaris", "uid", 0, "gid", 0, "dmode", 0755, "fmode", 0755);')
    info.script.AppendExtra('run_program("/tmp/lunaris/lunaris_config.sh");')
  return

def OTA_InstallEnd(info):
  info.script.Print("Patching firmware & hardware configuration...")

  vayu_prebuilt = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "vayu", "prebuilt"))
  dtbo_120 = os.path.join(vayu_prebuilt, "dtbo_120.img")
  dtbo_130 = os.path.join(vayu_prebuilt, "dtbo_130.img")
  boot_675 = os.path.join(vayu_prebuilt, "boot_675.img")

  has_vayu_selector = os.path.exists(dtbo_120) and os.path.exists(dtbo_130)

  if has_vayu_selector:
    # 1. Package both DTBO options
    AddFileToZip(info, dtbo_120, "dtbo_120.img")
    AddFileToZip(info, dtbo_130, "dtbo_130.img")

    # 2. Package stock 675MHz boot image
    if not os.path.exists(boot_675):
      try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "installer"))
        from generate_boot_675 import generate_boot_675
        boot_src = os.path.join(vayu_prebuilt, "boot.img")
        if not os.path.exists(boot_src):
          boot_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../out/target/product/vayu/boot.img"))
        if os.path.exists(boot_src):
          generate_boot_675(boot_src, boot_675)
      except Exception:
        pass

    if os.path.exists(boot_675):
      AddFileToZip(info, boot_675, "boot_675.img")

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
    if os.path.exists(boot_675):
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
