import pytest
from backend.services.sandbox_executor import SandboxExecutor
from backend.scenarios import (
    cloudflare_edge_outage,
    pydantic_schema_regression,
    redis_connection_leak
)

def test_sandbox_cloudflare_patch():
    scenario = cloudflare_edge_outage.get_scenario_data()
    rem = scenario["remediation"]
    result = SandboxExecutor.execute_regression_suite(
        target_file=rem.target_file,
        code_content=rem.patched_code_snippet,
        test_content=rem.regression_test_code
    )
    assert result.verified_safe is True
    assert result.tests_passed >= 1
    assert result.exit_code == 0

def test_sandbox_pydantic_patch():
    scenario = pydantic_schema_regression.get_scenario_data()
    rem = scenario["remediation"]
    result = SandboxExecutor.execute_regression_suite(
        target_file=rem.target_file,
        code_content=rem.patched_code_snippet,
        test_content=rem.regression_test_code
    )
    assert result.verified_safe is True
    assert result.tests_passed >= 1
    assert result.exit_code == 0

def test_sandbox_redis_patch():
    scenario = redis_connection_leak.get_scenario_data()
    rem = scenario["remediation"]
    result = SandboxExecutor.execute_regression_suite(
        target_file=rem.target_file,
        code_content=rem.patched_code_snippet,
        test_content=rem.regression_test_code
    )
    assert result.verified_safe is True
    assert result.tests_passed >= 1
    assert result.exit_code == 0

def test_sandbox_catches_broken_code():
    broken_code = "def faulty(): return 1 / 0\n"
    failing_test = "def test_fail(): from broken import faulty; assert faulty() == 1\n"
    result = SandboxExecutor.execute_regression_suite(
        target_file="broken.py",
        code_content=broken_code,
        test_content=failing_test
    )
    assert result.verified_safe is False
    assert result.tests_failed >= 1
