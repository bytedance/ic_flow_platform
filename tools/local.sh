#!/bin/bash

missing=false
for var in UUID USER_COMMAND IFP_LOG_FILE BLOCK VERSION TASK ACTION; do
    if [[ -z "${!var}" ]]; then
        echo "[ERROR] Missing environment variable: $var"
        missing=true
    fi
done

if [[ "$missing" = true ]]; then
    exit 100
fi

LOG_DIR="${IFP_LOG_FILE}"

STDOUT_LOG="${LOG_DIR}/${BLOCK}_${VERSION}_${TASK}_${ACTION}.stdout.log"
STDERR_LOG="${LOG_DIR}/${BLOCK}_${VERSION}_${TASK}_${ACTION}.stderr.log"
META_FILE="${LOG_DIR}/${BLOCK}_${VERSION}_${TASK}_${ACTION}.job.json"

rm -f "$STDOUT_LOG" "$STDERR_LOG" "$META_FILE"

START_TIME=$(date +%s)

eval "$USER_COMMAND > \"$STDOUT_LOG\" 2> \"$STDERR_LOG\"" &
ACTUAL_PID=$!
wait $ACTUAL_PID
RET_CODE=$?

END_TIME=$(date +%s)

cat <<EOF > "$META_FILE"
{
  "uuid": "$UUID",
  "start_time": $START_TIME,
  "end_time": $END_TIME,
  "return_code": $RET_CODE,
  "host": "$(hostname)",
  "pid": $ACTUAL_PID,
  "log_stdout": "$STDOUT_LOG",
  "log_stderr": "$STDERR_LOG"
}
EOF