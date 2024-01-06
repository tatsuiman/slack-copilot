import sys
import os

sys.path.append("../../src/scripts")
from ai import create_thread, create_run, create_message, run_assistant


def callback(completion="no message", files=[]):
    print(completion)
    if files:
        print(files)


assistant_id = os.getenv("TEST_ASSISTANT_ID")
thread = create_thread()
thread_id = thread.id
prompt = "こんにちは"
files = []
additional_instructions = ""
# メッセージを作成する
create_message(thread_id, prompt, files)
# Run IDを生成する

run_id = create_run(thread_id, assistant_id, additional_instructions)

res = run_assistant(run_id, thread_id, callback)
