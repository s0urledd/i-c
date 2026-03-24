# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
from dataclasses import dataclass
import typing


@allow_storage
@dataclass
class CaseData:
    plaintiff: Address
    defendant: Address
    plaintiff_argument: str
    defendant_argument: str
    status: str
    verdict: str
    reasoning: str
    awarded_to: str


class AIArbitration(gl.Contract):
    cases: TreeMap[u256, CaseData]
    case_count: u256

    def __init__(self):
        self.case_count = u256(0)

    @gl.public.write
    def create_case(self, defendant_address: Address) -> None:
        defendant = defendant_address
        plaintiff = gl.message.sender_address

        if plaintiff == defendant:
            raise gl.UserError("Cannot create case against yourself")

        case_id = u256(self.case_count)
        self.cases[case_id] = gl.storage.inmem_allocate(
            CaseData,
            plaintiff,
            defendant,
            "",
            "",
            "open",
            "",
            "",
            "",
        )
        self.case_count = u256(case_id + 1)

    @gl.public.write
    def submit_argument(self, case_id: int, argument: str) -> None:
        cid = u256(case_id)
        case = self.cases[cid]
        sender = gl.message.sender_address

        if case.status == "resolved":
            raise gl.UserError("Case already resolved")

        if sender == case.plaintiff:
            if case.plaintiff_argument != "":
                raise gl.UserError("Plaintiff already submitted argument")
            self.cases[cid].plaintiff_argument = argument
        elif sender == case.defendant:
            if case.defendant_argument != "":
                raise gl.UserError("Defendant already submitted argument")
            self.cases[cid].defendant_argument = argument
        else:
            raise gl.UserError("Only plaintiff or defendant can submit arguments")

        # Check if both arguments are submitted
        updated_case = self.cases[cid]
        if updated_case.plaintiff_argument != "" and updated_case.defendant_argument != "":
            self.cases[cid].status = "submitted"

    @gl.public.write
    def resolve(self, case_id: int) -> typing.Any:
        cid = u256(case_id)
        case = self.cases[cid]

        if case.status != "submitted":
            raise gl.UserError(
                "Case not ready for resolution. Both parties must submit arguments."
            )

        # Copy ENTIRE case to memory at once
        case_mem = gl.storage.copy_to_memory(case)

        prompt = f"""You are an impartial AI arbitrator. Analyze the following dispute and render a verdict.

CASE #{case_id}

PLAINTIFF ARGUES:
{case_mem.plaintiff_argument}

DEFENDANT ARGUES:
{case_mem.defendant_argument}

Respond ONLY as JSON with these exact keys:
{{
    "verdict": "A clear one-sentence verdict stating the outcome",
    "reasoning": "Detailed explanation of your reasoning",
    "awarded_to": "plaintiff" or "defendant" or "neither"
}}
"""

        def leader_fn():
            result = gl.nondet.exec_prompt(prompt, response_format="json")
            if not isinstance(result, dict):
                raise gl.UserError("LLM returned invalid format")
            if result.get("awarded_to") not in ("plaintiff", "defendant", "neither"):
                raise gl.UserError(
                    f"Invalid awarded_to value: {result.get('awarded_to')}"
                )
            return result

        def validator_fn(leader_result) -> bool:
            if not isinstance(leader_result, gl.vm.Return):
                return False
            validator_data = leader_fn()
            leader_data = leader_result.calldata
            # Compare only the decision field, not subjective reasoning
            return leader_data.get("awarded_to") == validator_data.get("awarded_to")

        result = gl.vm.run_nondet_unsafe(leader_fn, validator_fn)

        # Write to storage AFTER consensus
        self.cases[cid].verdict = result["verdict"]
        self.cases[cid].reasoning = result["reasoning"]
        self.cases[cid].awarded_to = result["awarded_to"]
        self.cases[cid].status = "resolved"

        return result

    @gl.public.view
    def get_case(self, case_id: int) -> typing.Any:
        cid = u256(case_id)
        case = self.cases[cid]
        return {
            "case_id": case_id,
            "plaintiff": case.plaintiff.as_hex,
            "defendant": case.defendant.as_hex,
            "plaintiff_argument": case.plaintiff_argument,
            "defendant_argument": case.defendant_argument,
            "status": case.status,
            "verdict": case.verdict,
            "reasoning": case.reasoning,
            "awarded_to": case.awarded_to,
        }

    @gl.public.view
    def get_case_count(self) -> int:
        return self.case_count
