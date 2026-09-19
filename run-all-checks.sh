#!/usr/bin/env bash
# rich4-spec · 一键自检
#
# 依次校验：机械层产物是否可重建、规格文档是否可复核、差分测试是否通过。
# 任何一步失败都非零退出。
#
# 用法：bash run-all-checks.sh
set -uo pipefail
cd "$(dirname "$0")"

PY=python3
VENV_PY=.venv/bin/python
fail=0

step() { printf '\n\033[1m── %s ──\033[0m\n' "$1"; }
ok()   { printf '  ✅ %s\n' "$1"; }
bad()  { printf '  ❌ %s\n' "$1"; fail=1; }

step "1/5 机械层可重建（代码）"
if $PY tools/rich4dis.py build --orphans >/tmp/rd.log 2>&1; then
  ok "$(grep -c . /tmp/rd.log) 行输出；$(grep -o '函数 [0-9]* 个' /tmp/rd.log | tail -1)"
else
  bad "rich4dis build 失败"; tail -5 /tmp/rd.log
fi

step "2/5 机械层可重建（数据）"
if $PY tools/rich4strings.py build >/tmp/rs.log 2>&1; then
  ok "$(grep -o '共 [0-9]* 条' /tmp/rs.log | head -1)"
else
  bad "rich4strings build 失败"; tail -5 /tmp/rs.log
fi

step "2.2/5 函数注解库（gen/db.txt）"
if $PY tools/annotate.py build >/tmp/an.log 2>&1; then
  ok "$(grep -o 'db.txt（[0-9]* 行）' /tmp/an.log)"
else
  bad "annotate build 失败"; tail -5 /tmp/an.log
fi

step "3/5 规格文档质检"
if $PY tools/lint_specs.py >/tmp/lint.log 2>&1; then
  ok "$(tail -1 /tmp/lint.log)"
else
  bad "质检有错误"; grep -E '❌|合计' /tmp/lint.log
fi

step "3.2/5 逐函数覆盖（阶段 1 的可复算数字）"
if $PY tools/audit_spec_coverage.py >/tmp/cov.log 2>&1; then
  # 只报两个关键数：PRD 覆盖率、以及「有调用者却未提」的真·遗漏数
  cov=$(grep -o '被规格提到 [0-9]* 个.*【' /tmp/cov.log | head -1)
  cov=$(grep '被规格提到' /tmp/cov.log | head -1)
  miss=$(grep '桶 \[4\]' /tmp/cov.log | head -1)
  ok "${cov:-已生成}；${miss:-—}"
else
  bad "audit_spec_coverage 失败"; tail -5 /tmp/cov.log
fi

step "3.25/5 数据表覆盖门禁（104 张 table:data）"
if $PY tools/audit_data_tables.py >/tmp/dtbl.log 2>&1; then
  ok "$(tail -1 /tmp/dtbl.log)"
else
  bad "有数据表没进 PRD"; grep '✘' /tmp/dtbl.log | head -5
fi

step "3.3/5 镜像覆盖（PRD 写了、remake 没提 —— 只报 A 桶）"
if $PY tools/audit_unimplemented.py >/tmp/uimpl.log 2>&1; then
  ok "$(grep -o '\[A\] 有调用者.*' /tmp/uimpl.log | head -1)"
else
  bad "audit_unimplemented 失败"; tail -5 /tmp/uimpl.log
fi

step "3.4/5 通道 2 待测工作单（可复算：还有多少规则函数没差分过）"
if $PY tools/audit_channel2_targets.py --limit 0 >/tmp/c2.log 2>&1; then
  ok "$(head -1 /tmp/c2.log)"
else
  bad "audit_channel2_targets 失败"; tail -5 /tmp/c2.log
fi

step "3.45/5 随机数调用点普查（规则 vs 表现——确定性用）"
if $PY tools/audit_rng_sites.py >/tmp/rng.log 2>&1; then
  ok "$(head -1 /tmp/rng.log) / $(grep -c '处$' /tmp/rng.log) 行分布"
else
  bad "audit_rng_sites 失败"; tail -5 /tmp/rng.log
fi

step "3.5/5 轨迹比对工具自检（通道 3）"
if $PY tools/difftrace.py selftest >/tmp/dt.log 2>&1; then
  ok "$(tail -1 /tmp/dt.log)"
else
  bad "difftrace selftest 失败"; tail -5 /tmp/dt.log
fi

step "3.55/5 强口径覆盖：CALL 档 + 跳表档（两层都必须 0）"
if $PY tools/audit_call_targets.py --strict --strict-jt >/tmp/ct.log 2>&1; then
  ok "$(grep -m1 'CALL 档' /tmp/ct.log)"
  ok "$(grep -m1 'JT 档' /tmp/ct.log)"
else
  bad "强口径覆盖非空 —— 有子程序/跳表处理器被调用但 PRD 没写"; grep '^【' /tmp/ct.log
fi

step "4/5 差分测试（通道 2）"
if [ -x "$VENV_PY" ]; then
  rc=0
  for t in tests/test_*.py; do
    [ -e "$t" ] || continue
    if out=$($VENV_PY "$t" 2>&1); then
      ok "$t → $(echo "$out" | tail -1)"
    else
      bad "$t 失败"; echo "$out" | grep -E '❌|Error|错误' | head -5
      rc=1
    fi
  done
  [ $rc -eq 0 ] || fail=1
else
  printf '  ⚠️  未找到 .venv，跳过差分测试（建法见 docs/verification.md）\n'
fi

if [ $fail -eq 0 ]; then
  printf '\n\033[32m全部通过\033[0m\n'
else
  printf '\n\033[31m有失败项\033[0m\n'
fi
exit $fail
