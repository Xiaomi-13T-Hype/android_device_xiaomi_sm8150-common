#!/sbin/sh
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

wait_key_selection() {
    local default_val="$1"
    local opt_plus="$2"
    local opt_minus="$3"
    local timeout_sec=10
    local choice="$default_val"
    local key_file="/tmp/lunaris_key"

    rm -f "$key_file"

    # Start background key event listener
    (
        getevent -l 2>/dev/null | while read -r line; do
            case "$line" in
                *KEY_VOLUMEUP*DOWN*|*0073*00000001*|*0073*1*)
                    echo "$opt_plus" > "$key_file"
                    exit 0
                    ;;
                *KEY_VOLUMEDOWN*DOWN*|*0072*00000001*|*0072*1*)
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
            choice=$(cat "$key_file")
            break
        fi
        sleep 1
        elapsed=$((elapsed + 1))
        local remaining=$((timeout_sec - elapsed))
        if [ $remaining -gt 0 ] && [ $((remaining % 3)) -eq 0 ]; then
            ui_print "  ... remaining: $remaining s"
        fi
    done

    kill -9 $listener_pid 2>/dev/null
    killall getevent 2>/dev/null
    rm -f "$key_file"
    sleep 1

    echo "$choice"
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
ui_print "  [VOLUME -] Overclocked 130Hz "
ui_print "  (Timeout 10 sec -> Stock 120Hz)"

DISP_CHOICE=$(wait_key_selection "120" "120" "130")

if [ "$DISP_CHOICE" = "130" ]; then
    ui_print ">> Selected: [Overcloked 130Hz ]"
else
    ui_print ">> Selected: [Stock 120Hz]"
    DISP_CHOICE="120"
fi

ui_print " "

# Step 2: GPU Clock
ui_print "[2/2] Max GPU Frequency:"
ui_print "  [VOLUME +] Stock GPU (675MHz)"
ui_print "  [VOLUME -] Overcloked GPU (692MHz)"
ui_print "  (Timeout 10 sec -> Stock GPU (675MHz)"

GPU_CHOICE=$(wait_key_selection "675" "675" "692")

if [ "$GPU_CHOICE" = "692" ]; then
    ui_print ">> Selected: [Overcloked GPU (692MHz)]"
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
