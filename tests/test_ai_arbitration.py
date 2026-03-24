import json


def test_create_case(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/ai_arbitration.py")

    direct_vm.sender = direct_alice
    contract.create_case(str(direct_bob))

    assert contract.get_case_count() == 1

    case = contract.get_case(0)
    assert case["plaintiff"] == str(direct_alice)
    assert case["defendant"] == str(direct_bob)
    assert case["status"] == "open"


def test_submit_arguments(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/ai_arbitration.py")

    direct_vm.sender = direct_alice
    contract.create_case(str(direct_bob))

    # Alice submits argument
    contract.submit_argument(0, "Bob owes me 100 tokens for services rendered")

    case = contract.get_case(0)
    assert case["status"] == "open"

    # Bob submits argument
    direct_vm.sender = direct_bob
    contract.submit_argument(0, "I already paid Alice in full")

    case = contract.get_case(0)
    assert case["status"] == "submitted"


def test_resolve_case(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/ai_arbitration.py")

    direct_vm.sender = direct_alice
    contract.create_case(str(direct_bob))
    contract.submit_argument(0, "Bob broke our agreement and failed to deliver")

    direct_vm.sender = direct_bob
    contract.submit_argument(0, "I did not break anything, the terms were unclear")

    # Mock the LLM response
    direct_vm.mock_llm(
        r".*impartial AI arbitrator.*",
        json.dumps(
            {
                "verdict": "The plaintiff's claim is upheld due to breach of agreement",
                "reasoning": "Based on the arguments presented, the plaintiff provided a clear claim of breach. The defendant's response does not adequately refute the claim.",
                "awarded_to": "plaintiff",
            }
        ),
    )

    direct_vm.sender = direct_alice
    contract.resolve(0)

    case = contract.get_case(0)
    assert case["status"] == "resolved"
    assert case["awarded_to"] == "plaintiff"
    assert case["verdict"] != ""
    assert case["reasoning"] != ""


def test_cannot_create_case_against_self(
    direct_vm, direct_deploy, direct_alice
):
    contract = direct_deploy("contracts/ai_arbitration.py")

    direct_vm.sender = direct_alice
    try:
        contract.create_case(str(direct_alice))
        assert False, "Should have raised an error"
    except Exception:
        pass


def test_cannot_submit_twice(direct_vm, direct_deploy, direct_alice, direct_bob):
    contract = direct_deploy("contracts/ai_arbitration.py")

    direct_vm.sender = direct_alice
    contract.create_case(str(direct_bob))
    contract.submit_argument(0, "First argument")

    try:
        contract.submit_argument(0, "Second argument")
        assert False, "Should have raised an error"
    except Exception:
        pass


def test_cannot_resolve_before_both_submit(
    direct_vm, direct_deploy, direct_alice, direct_bob
):
    contract = direct_deploy("contracts/ai_arbitration.py")

    direct_vm.sender = direct_alice
    contract.create_case(str(direct_bob))
    contract.submit_argument(0, "My argument")

    try:
        contract.resolve(0)
        assert False, "Should have raised an error"
    except Exception:
        pass
