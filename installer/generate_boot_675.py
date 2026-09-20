#!/usr/bin/env python3
#
# Generates a stock 675MHz GPU boot image from a given SM8150 boot image
# by removing opp-692000000 and restoring stock GPU opp/pwrlevels in DTB.
#

import os
import sys
import tempfile
import shutil
import subprocess
import struct
import re

def generate_boot_675(boot_src_path, boot_dst_path, top_dir=None):
    if top_dir is None:
        top_dir = os.environ.get("ANDROID_BUILD_TOP", os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))

    dtc = os.path.join(top_dir, "prebuilts/kernel-build-tools/linux-x86/bin/dtc")
    mkbootimg = os.path.join(top_dir, "system/tools/mkbootimg/mkbootimg.py")
    unpack_bootimg = os.path.join(top_dir, "system/tools/mkbootimg/unpack_bootimg.py")

    tmpdir = tempfile.mkdtemp(prefix="boot_675_")
    try:
        # 1. Unpack boot image
        subprocess.run(["python3", unpack_bootimg, "--boot_img", boot_src_path, "--out", tmpdir], check=True, stdout=subprocess.DEVNULL)

        # 2. Extract and split DTBs
        with open(os.path.join(tmpdir, "dtb"), "rb") as f:
            dtb_data = f.read()

        pos = 0
        blobs = []
        while pos < len(dtb_data):
            magic, size = struct.unpack(">II", dtb_data[pos:pos+8])
            if magic != 0xd00dfeed:
                break
            blobs.append(dtb_data[pos:pos+size])
            pos += size

        # 3. Patch sm8150-v2 and sm8150p-v2 blobs (indices 1 and 3)
        patched_blobs = []
        for i, blob in enumerate(blobs):
            if i in (1, 3):
                dts = subprocess.check_output([dtc, "-I", "dtb", "-O", "dts"], input=blob, stderr=subprocess.DEVNULL).decode("utf-8")
                # Remove opp-692000000 node
                dts = re.sub(r'\t+opp-692000000\s*\{[^}]*\};\n?', '', dts)
                # Replace 692MHz with 675MHz in any gpu-freq property
                dts = dts.replace("<0x293f1500>", "<0x283baec0>")
                recompiled = subprocess.check_output([dtc, "-I", "dts", "-O", "dtb"], input=dts.encode("utf-8"), stderr=subprocess.DEVNULL)
                patched_blobs.append(recompiled)
            else:
                patched_blobs.append(blob)

        dtb_out = os.path.join(tmpdir, "dtb_675.img")
        with open(dtb_out, "wb") as f:
            for b in patched_blobs:
                f.write(b)

        # 4. Pack boot_675.img
        cmd = [
            "python3", mkbootimg,
            "--kernel", os.path.join(tmpdir, "kernel"),
            "--ramdisk", os.path.join(tmpdir, "ramdisk"),
            "--dtb", dtb_out,
            "--cmdline", "androidboot.hardware=qcom androidboot.console=ttyMSM0 androidboot.memcg=1 lpm_levels.sleep_disabled=1 msm_rtb.filter=0x237 service_locator.enable=1 swiotlb=2048 loop.max_part=7 androidboot.usbcontroller=a600000.dwc3 androidboot.fstab_suffix=qcom androidboot.init_fatal_reboot_target=recovery",
            "--base", "0x00000000",
            "--pagesize", "4096",
            "--kernel_offset", "0x00008000",
            "--ramdisk_offset", "0x01000000",
            "--tags_offset", "0x00000100",
            "--dtb_offset", "0x01f00000",
            "--os_version", "16.0.0",
            "--os_patch_level", "2026-09",
            "--header_version", "2",
            "--output", boot_dst_path
        ]
        subprocess.run(cmd, check=True)

        # Pad to 134217728 bytes (128MB) to match partition size
        with open(boot_dst_path, "ab") as f:
            cur_len = f.tell()
            pad = 134217728 - cur_len
            if pad > 0:
                f.write(b"\x00" * pad)

    finally:
        shutil.rmtree(tmpdir)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: generate_boot_675.py <input_boot.img> <output_boot_675.img>")
        sys.exit(1)
    generate_boot_675(sys.argv[1], sys.argv[2])
