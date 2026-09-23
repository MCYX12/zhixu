#!/bin/zsh
cd -- "${0:A:h}" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  print '缺少本地 Python 环境，请先按 README 完成安装。'
  read '?按回车关闭窗口'
  exit 1
fi
.venv/bin/python scripts/start_workspace.py "$@"
result=$?
if (( result != 0 )); then
  read '?按回车关闭窗口'
fi
exit $result
