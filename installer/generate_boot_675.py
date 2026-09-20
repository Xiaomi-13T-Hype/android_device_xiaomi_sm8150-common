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

def find_top_dir(top_dir=None):
    if top_dir and os.path.isdir(os.path.join(top_dir, "device", "xiaomi", "sm8150-common")):
        return top_dir

    env_top = os.environ.get("ANDROID_BUILD_TOP")
    if env_top and os.path.isdir(os.path.join(env_top, "device", "xiaomi", "sm8150-common")):
        return env_top

    cwd = os.getcwd()
    if os.path.isdir(os.path.join(cwd, "device", "xiaomi", "sm8150-common")):
        return cwd

    script_top = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    if os.path.isdir(os.path.join(script_top, "device", "xiaomi", "sm8150-common")):
        return script_top

    if os.path.isdir("/home/Ximi/Poco-X3-Pro-Lunaris-AOSP"):
        return "/home/Ximi/Poco-X3-Pro-Lunaris-AOSP"

    return None

def generate_boot_675(boot_src_path, boot_dst_path, top_dir=None):
    top = find_top_dir(top_dir)
    if not top:
        raise RuntimeError("Could not determine Android build top directory")

    dtc = os.path.join(top, "prebuilts/kernel-build-tools/linux-x86/bin/dtc")
    if not os.path.exists(dtc):
        dtc = shutil.which("dtc")
    if not dtc or not os.path.exists(dtc):
        raise RuntimeError("dtc binary not found")

    mkbootimg = os.path.join(top, "system/tools/mkbootimg/mkbootimg.py")
    unpack_bootimg = os.path.join(top, "system/tools/mkbootimg/unpack_bootimg.py")

    if not os.path.exists(mkbootimg) or not os.path.exists(unpack_bootimg):
        raise RuntimeError("mkbootimg/unpack_bootimg tools not found in system/tools/mkbootimg")

    tmpdir = tempfile.mkdtemp(prefix="boot_675_")
    try:
        # 1. Unpack boot image with mkbootimg argument extraction (-0)
        raw_args = subprocess.check_output(
            ["python3", unpack_bootimg, "--boot_img", boot_src_path, "--out", tmpdir, "--format", "mkbootimg", "-0"]
        )
        unpacked_args = raw_args.decode("utf-8").split("\0")
        if unpacked_args and unpacked_args[-1] == "":
            unpacked_args.pop()

        # 2. Extract and split DTBs
        dtb_file = os.path.join(tmpdir, "dtb")
        if not os.path.exists(dtb_file):
            raise RuntimeError("No DTB found in unpacked boot image")

        with open(dtb_file, "rb") as f:
            dtb_data = f.read()

        pos = 0
        blobs = []
        while pos < len(dtb_data):
            if pos + 8 > len(dtb_data):
                break
            magic, size = struct.unpack(">II", dtb_data[pos:pos+8])
            if magic != 0xd00dfeed:
                break
            blobs.append(dtb_data[pos:pos+size])
            pos += size

        # 3. Patch blobs containing 692MHz GPU opp table
        patched_blobs = []
        for i, blob in enumerate(blobs):
            dts = subprocess.check_output([dtc, "-I", "dtb", "-O", "dts"], input=blob, stderr=subprocess.DEVNULL).decode("utf-8")
            if "692000000" in dts or "<0x293f1500>" in dts:
                # Transform 692MHz OPP and frequency to 675MHz maintaining 7-level GMU table
                dts = dts.replace("opp-692000000", "opp-675000000")
                dts = dts.replace("692000000", "675000000")
                dts = dts.replace("<0x293f1500>", "<0x283baec0>")
                recompiled = subprocess.check_output([dtc, "-I", "dts", "-O", "dtb"], input=dts.encode("utf-8"), stderr=subprocess.DEVNULL)
                patched_blobs.append(recompiled)
            else:
                patched_blobs.append(blob)

        dtb_out = os.path.join(tmpdir, "dtb_675.img")
        with open(dtb_out, "wb") as f:
            for b in patched_blobs:
                f.write(b)

        # 4. Filter unpacked args and substitute --dtb with patched dtb
        repack_args = []
        skip_next = False
        for arg in unpacked_args:
            if skip_next:
                skip_next = False
                continue
            if arg == "--dtb":
                repack_args.extend(["--dtb", dtb_out])
                skip_next = True
            elif arg == "--output":
                skip_next = True
            else:
                repack_args.append(arg)

        cmd = ["python3", mkbootimg] + repack_args + ["--output", boot_dst_path]
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
        print("Usage: generate_boot_675.py <input_boot.img> <output_boot_675.img> [top_dir]")
        sys.exit(1)
    top_arg = sys.argv[3] if len(sys.argv) > 3 else None
    generate_boot_675(sys.argv[1], sys.argv[2], top_dir=top_arg)
