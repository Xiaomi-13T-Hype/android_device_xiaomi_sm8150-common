#!/sbin/sh
#
# Lunaris AOSP Hardware Frequency Selector for Poco X3 Pro (vayu)
# Runs during recovery installation to configure Display (120/130Hz) and GPU (675/692MHz).
#

CHOICE_PROP="/tmp/lunaris_choice.prop"
FIFO="/tmp/lunaris_ev_fifo"

# Detect Recovery command pipe (status_fd passed to update_binary)
OUTFD=
if [ -r "/proc/$PPID/cmdline" ]; then
    PARENT_FD=$(tr '\0' '\n' < "/proc/$PPID/cmdline" 2>/dev/null | sed -n '3p')
    if [ -n "$PARENT_FD" ] && [ -e "/proc/$$/fd/$PARENT_FD" ]; then
        OUTFD="/proc/$$/fd/$PARENT_FD"
    fi
fi

# Fallback pipe search if parent cmdline did not resolve
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

ui_print() {
    if [ -n "$OUTFD" ]; then
        echo "ui_print $1" > "$OUTFD" 2>/dev/null
        echo "ui_print" > "$OUTFD" 2>/dev/null
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

    rm -f "$FIFO"
    mknod "$FIFO" p 2>/dev/null || mkfifo "$FIFO" 2>/dev/null

    # Run getevent in background sending to FIFO
    getevent -lq > "$FIFO" 2>/dev/null &
    local ev_pid=$!

    # Open descriptor 3 on FIFO
    exec 3< "$FIFO"

    local elapsed=0
    while [ $elapsed -lt $timeout_sec ]; do
        if read -t 1 line <&3; then
            case "$line" in
                *KEY_VOLUMEUP*DOWN*|*0073*00000001*|*0073*1*)
                    choice="$opt_plus"
                    break
                    ;;
                *KEY_VOLUMEDOWN*DOWN*|*0072*00000001*|*0072*1*)
                    choice="$opt_minus"
                    break
                    ;;
            esac
        else
            elapsed=$((elapsed + 1))
            local remaining=$((timeout_sec - elapsed))
            if [ $remaining -gt 0 ] && [ $((remaining % 3)) -eq 0 ]; then
                ui_print "  ... осталось $remaining сек"
            fi
        fi
    done

    # Cleanup getevent
    exec 3<&-
    kill -9 $ev_pid 2>/dev/null
    wait $ev_pid 2>/dev/null
    rm -f "$FIFO"

    # Debounce delay to prevent double-click onto step 2
    sleep 1

    echo "$choice"
}

# --- Main Selector Interface ---

ui_print " "
ui_print "==============================================="
ui_print "       LUNARIS AOSP HARDWARE SELECTOR"
ui_print "==============================================="
ui_print " "

# Step 1: Display Refresh Rate
ui_print "[1/2] Частота обновления экрана:"
ui_print "  [ГРОМКОСТЬ +] Сток 120 Гц (Рекомендуется)"
ui_print "  [ГРОМКОСТЬ -] Разгон 130 Гц (Плавный режим)"
ui_print "  (Таймаут 10 сек -> Сток 120 Гц)"

DISP_CHOICE=$(wait_key_selection "120" "120" "130")

if [ "$DISP_CHOICE" = "130" ]; then
    ui_print ">> ВЫБРАНО: [Разгон 130 Гц]"
else
    ui_print ">> ВЫБРАНО: [Сток 120 Гц]"
    DISP_CHOICE="120"
fi

ui_print " "

# Step 2: GPU Clock
ui_print "[2/2] Максимальная частота GPU Adreno 640:"
ui_print "  [ГРОМКОСТЬ +] Сток 675 МГц (Холодный / Стабильный)"
ui_print "  [ГРОМКОСТЬ -] Разгон 692 МГц (Макс. FPS)"
ui_print "  (Таймаут 10 сек -> Сток 675 МГц)"

GPU_CHOICE=$(wait_key_selection "675" "675" "692")

if [ "$GPU_CHOICE" = "692" ]; then
    ui_print ">> ВЫБРАНО: [Разгон 692 МГц]"
else
    ui_print ">> ВЫБРАНО: [Сток 675 МГц]"
    GPU_CHOICE="675"
fi

ui_print " "
ui_print "==============================================="
ui_print " КОНФИГУРАЦИЯ СОХРАНЕНА:"
ui_print "  - Экран : ${DISP_CHOICE} Гц"
ui_print "  - GPU   : ${GPU_CHOICE} МГц"
ui_print " Приступаем к распаковке и установке..."
ui_print "==============================================="
ui_print " "

# Save properties to /tmp/lunaris_choice.prop
mkdir -p "$(dirname "$CHOICE_PROP")"
echo "display_hz=${DISP_CHOICE}" > "$CHOICE_PROP"
echo "gpu_clock=${GPU_CHOICE}" >> "$CHOICE_PROP"

exit 0
