#!/vendor/bin/sh
# Copyright (c) 2012-2018, 2020 The Linux Foundation. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#     * Neither the name of The Linux Foundation nor the names of its
#       contributors may be used to endorse or promote products derived
#      from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY EXPRESS OR IMPLIED
# WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN
# IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#

# Set platform variables
soc_hwplatform=`cat /sys/devices/soc0/hw_platform 2> /dev/null`
soc_machine=`cat /sys/devices/soc0/machine 2> /dev/null`
soc_machine=${soc_machine:0:2}
soc_id=`cat /sys/devices/soc0/soc_id 2> /dev/null`

#
# Allow USB enumeration with default PID/VID
#
baseband=`getprop ro.baseband`
debuggable=`getprop ro.debuggable`
buildvariant=`getprop ro.build.type`

#
# Check ESOC for external modem
#
# Note: currently only a single MDM/SDX is supported
#
esoc_name=`cat /sys/bus/esoc/devices/esoc0/esoc_name 2> /dev/null`

target=`getprop ro.board.platform`

#
# Override USB default composition
# Clear vendor USB config because it is only needed for debugging
setprop persist.vendor.usb.config ""

# This check is needed for GKI 1.0 targets where QDSS is not available
if [ "$(getprop persist.vendor.usb.config)" == "diag,serial_cdev,rmnet,dpl,qdss,adb" -a \
     ! -d /config/usb_gadget/g1/functions/qdss.qdss ]; then
      setprop persist.vendor.usb.config diag,serial_cdev,rmnet,dpl,adb
fi

# Start peripheral mode on primary USB controllers for Automotive platforms
case "$soc_machine" in
    "SA")
	if [ -f /sys/bus/platform/devices/a600000.ssusb/mode ]; then
	    default_mode=`cat /sys/bus/platform/devices/a600000.ssusb/mode`
	    case "$default_mode" in
		"none")
		    echo peripheral > /sys/bus/platform/devices/a600000.ssusb/mode
		;;
	    esac
	fi
    ;;
esac

# check configfs is mounted or not
if [ -d /config/usb_gadget ]; then

	# ADB requires valid iSerialNumber; if ro.serialno is missing, use dummy
	serialnumber=`cat /config/usb_gadget/g1/strings/0x409/serialnumber 2> /dev/null`
	if [ "$serialnumber" == "" ]; then
		serialno=1234567
		echo $serialno > /config/usb_gadget/g1/strings/0x409/serialnumber
	fi

	setprop vendor.usb.configfs 1
fi

# update product
marketname=`getprop ro.product.marketname`
if [ "$marketname" != "" ]; then
    setprop vendor.usb.product_string "$marketname"
else
    setprop vendor.usb.product_string "$(getprop ro.product.model)"
fi

#
# Initialize RNDIS Diag option. If unset, set it to 'none'.
#
diag_extra=`getprop persist.vendor.usb.config.extra`
if [ "$diag_extra" == "" ]; then
	setprop persist.vendor.usb.config.extra none
fi

# enable rps cpus on msm8937 target
setprop vendor.usb.rps_mask 0
case "$soc_id" in
	"294" | "295" | "353" | "354")
		setprop vendor.usb.rps_mask 40
	;;
esac

#
#
# Initialize UVC configuration.
#
UVC_DIR="/config/usb_gadget/g1/functions/uvc.0"
if [ ! -d "${UVC_DIR}" ]; then
	mkdir -p "${UVC_DIR}"
fi

if [ -d "${UVC_DIR}" ]; then
	echo 3072 > "${UVC_DIR}/streaming_maxpacket"
	echo 10 > "${UVC_DIR}/streaming_maxburst"

	# Control header (default bcdUVC 0x0150 / UVC 1.50)
	mkdir -p "${UVC_DIR}/control/header/h"
	ln -s "${UVC_DIR}/control/header/h" "${UVC_DIR}/control/class/fs/h" 2>/dev/null || true
	ln -s "${UVC_DIR}/control/header/h" "${UVC_DIR}/control/class/ss/h" 2>/dev/null || true

	# Streaming uncompressed formats
	mkdir -p "${UVC_DIR}/streaming/uncompressed/u/360p"
	echo 640 > "${UVC_DIR}/streaming/uncompressed/u/360p/wWidth"
	echo 360 > "${UVC_DIR}/streaming/uncompressed/u/360p/wHeight"
	echo 18432000 > "${UVC_DIR}/streaming/uncompressed/u/360p/dwMinBitRate"
	echo 55296000 > "${UVC_DIR}/streaming/uncompressed/u/360p/dwMaxBitRate"
	echo 460800 > "${UVC_DIR}/streaming/uncompressed/u/360p/dwMaxVideoFrameBufferSize"
	echo 333333 > "${UVC_DIR}/streaming/uncompressed/u/360p/dwDefaultFrameInterval"
	printf '166666\n333333\n666666\n1000000\n5000000\n' > "${UVC_DIR}/streaming/uncompressed/u/360p/dwFrameInterval"

	mkdir -p "${UVC_DIR}/streaming/uncompressed/u/720p"
	echo 1280 > "${UVC_DIR}/streaming/uncompressed/u/720p/wWidth"
	echo 720 > "${UVC_DIR}/streaming/uncompressed/u/720p/wHeight"
	echo 29491200 > "${UVC_DIR}/streaming/uncompressed/u/720p/dwMinBitRate"
	echo 29491200 > "${UVC_DIR}/streaming/uncompressed/u/720p/dwMaxBitRate"
	echo 1843200 > "${UVC_DIR}/streaming/uncompressed/u/720p/dwMaxVideoFrameBufferSize"
	echo 333333 > "${UVC_DIR}/streaming/uncompressed/u/720p/dwDefaultFrameInterval"
	printf '166666\n333333\n666666\n1000000\n5000000\n' > "${UVC_DIR}/streaming/uncompressed/u/720p/dwFrameInterval"

	# Streaming mjpeg formats
	mkdir -p "${UVC_DIR}/streaming/mjpeg/m/360p"
	echo 640 > "${UVC_DIR}/streaming/mjpeg/m/360p/wWidth"
	echo 360 > "${UVC_DIR}/streaming/mjpeg/m/360p/wHeight"
	echo 18432000 > "${UVC_DIR}/streaming/mjpeg/m/360p/dwMinBitRate"
	echo 55296000 > "${UVC_DIR}/streaming/mjpeg/m/360p/dwMaxBitRate"
	echo 460800 > "${UVC_DIR}/streaming/mjpeg/m/360p/dwMaxVideoFrameBufferSize"
	echo 333333 > "${UVC_DIR}/streaming/mjpeg/m/360p/dwDefaultFrameInterval"
	printf '166666\n333333\n666666\n1000000\n5000000\n' > "${UVC_DIR}/streaming/mjpeg/m/360p/dwFrameInterval"

	mkdir -p "${UVC_DIR}/streaming/mjpeg/m/720p"
	echo 1280 > "${UVC_DIR}/streaming/mjpeg/m/720p/wWidth"
	echo 720 > "${UVC_DIR}/streaming/mjpeg/m/720p/wHeight"
	echo 29491200 > "${UVC_DIR}/streaming/mjpeg/m/720p/dwMinBitRate"
	echo 29491200 > "${UVC_DIR}/streaming/mjpeg/m/720p/dwMaxBitRate"
	echo 1843200 > "${UVC_DIR}/streaming/mjpeg/m/720p/dwMaxVideoFrameBufferSize"
	echo 333333 > "${UVC_DIR}/streaming/mjpeg/m/720p/dwDefaultFrameInterval"
	printf '166666\n333333\n666666\n1000000\n5000000\n' > "${UVC_DIR}/streaming/mjpeg/m/720p/dwFrameInterval"

	mkdir -p "${UVC_DIR}/streaming/mjpeg/m/1080p"
	echo 1920 > "${UVC_DIR}/streaming/mjpeg/m/1080p/wWidth"
	echo 1080 > "${UVC_DIR}/streaming/mjpeg/m/1080p/wHeight"
	echo 66355200 > "${UVC_DIR}/streaming/mjpeg/m/1080p/dwMinBitRate"
	echo 995328000 > "${UVC_DIR}/streaming/mjpeg/m/1080p/dwMaxBitRate"
	echo 4147200 > "${UVC_DIR}/streaming/mjpeg/m/1080p/dwMaxVideoFrameBufferSize"
	echo 333333 > "${UVC_DIR}/streaming/mjpeg/m/1080p/dwDefaultFrameInterval"
	printf '166666\n333333\n666666\n1000000\n5000000\n' > "${UVC_DIR}/streaming/mjpeg/m/1080p/dwFrameInterval"

	echo 0x04 > "${UVC_DIR}/streaming/mjpeg/m/bmaControls"

	# Streaming header & class links
	mkdir -p "${UVC_DIR}/streaming/header/h"
	ln -s "${UVC_DIR}/streaming/uncompressed/u" "${UVC_DIR}/streaming/header/h/u" 2>/dev/null || true
	ln -s "${UVC_DIR}/streaming/mjpeg/m" "${UVC_DIR}/streaming/header/h/m" 2>/dev/null || true
	ln -s "${UVC_DIR}/streaming/header/h" "${UVC_DIR}/streaming/class/fs/h" 2>/dev/null || true
	ln -s "${UVC_DIR}/streaming/header/h" "${UVC_DIR}/streaming/class/hs/h" 2>/dev/null || true
	ln -s "${UVC_DIR}/streaming/header/h" "${UVC_DIR}/streaming/class/ss/h" 2>/dev/null || true

	# Ownership and permissions for HAL
	chown -R system:usb "${UVC_DIR}" 2>/dev/null || chown -R 1000:1014 "${UVC_DIR}" 2>/dev/null
	chmod -R 0770 "${UVC_DIR}"
fi

if [ -d /config/usb_gadget/g1/functions/uac2.0 ]; then
	setprop vendor.usb.uac2.function.init 1
fi

