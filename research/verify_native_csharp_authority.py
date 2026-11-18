"""Read-only structural CI regression guard for future C#-authoritative studies.

This validates project graph and no-order boundary only. It does NOT attest
feature/model/decision numerical parity, authentic fees, economic alpha,
Cloud runtime, original broker fills or independent confirmation.
"""
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise AssertionError("NATIVE_CSHARP_AUTHORITY_" + reason)


def project(path: str):
    return ET.parse(ROOT / path).getroot()


def refs(path: str):
    return [e.attrib.get("Include", "").replace("\\", "/")
            for e in project(path).iter("ProjectReference")]


def verify() -> None:
    core = "src/Mxm.Core/Mxm.Core.csproj"
    replay = "src/Mxm.Replay/Mxm.Replay.csproj"
    cloud = "src/Mxm.Cloud/Mxm.Cloud.csproj"
    checks = "tests/Mxm.Checks/Mxm.Checks.csproj"
    require("net6.0" in (ROOT / core).read_text(),
            "CORE_CLOUD_TARGET_FRAMEWORK")
    for path in (replay, cloud, checks):
        reference = refs(path)
        require(any("Mxm.Core/Mxm.Core.csproj" in p for p in reference),
                "SHARED_CORE_PROJECT_REFERENCE_" + path.replace("/", "_"))
    cloud_source = (ROOT / "src/Mxm.Cloud/MxmCloud.cs").read_text()
    require("[Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]" in cloud_source,
            "NO_ORDER_CLOUD_ACCESS_RIGHTS")
    require("using Mxm.Core;" in cloud_source and
            "NativeProductResearchLoop" in cloud_source and
            "NativeFundedSession" in cloud_source,
            "CLOUD_USES_EXISTING_NATIVE_SHARED_RESEARCH")
    for forbidden in ("ExecuteMarketOrder(", "ExecuteMarketRangeOrder(",
                      "PlaceLimitOrder(", "PlaceStopOrder(",
                      "ModifyPosition(", "ClosePosition("):
        require(forbidden not in cloud_source,
                "NO_ORDER_BOUNDARY_" + forbidden.split("(")[0])
    require((ROOT / "src/Mxm.Core/NativeAuthorityBoundary.cs").is_file(),
            "FUTURE_ECONOMIC_AUTHORITY_IN_CORE")
    tests = (ROOT / "tests/Mxm.Checks/Program.cs").read_text()
    require("NativeAuthorityBoundaryChecks.Run(Check);" in tests,
            "C_SHARP_AUTHORITY_GATE_COVERAGE")
    ci = (ROOT / ".github/workflows/verify.yml").read_text()
    for command in ("dotnet run --project tests/Mxm.Checks -c Release",
                    "dotnet build src/Mxm.Replay -c Release",
                    "dotnet build src/Mxm.Cloud -c Release"):
        require(command in ci, "EXISTING_NATIVE_CI_COMMAND_" +
                command.split("/")[-1].replace(" ", "_"))
    spec = (ROOT / "docs/OWNER_SPEC.md").read_text()
    require("OWNER prospective single C# authority — 2026-11-18" in spec,
            "ACTIVE_OWNER_SINGLE_CSHARP_MANDATE")
    owner = (ROOT / "src/Mxm.Core/OwnerRiskLimits.cs").read_text()
    for invariant in ("InitialCapitalEur=300m",
                      "MaximumSystemDrawdown=.30m",
                      "MinimumSystemRoundTripsPerEligibleWeek=21"):
        require(invariant in owner, "OWNER_INVARIANT_" + invariant.split("=")[0])
    # Prospective entry points must reuse the single C# Core engine; a Python
    # research-only receipt auditor is allowed but is never a second scorer.
    core_study = (ROOT / "src/Mxm.Core/NativeBayesianCommonEpisode.cs").read_text()
    replay_study = (ROOT / "src/Mxm.Replay/OwnerNativeBayesParity.cs").read_text()
    cloud_adapter = (ROOT / "src/Mxm.Cloud/NativeCloudResearchParityAdapter.cs").read_text()
    replay_project = (ROOT / "src/Mxm.Replay/Mxm.Replay.csproj").read_text()
    require("class NativeBayesianCommonEpisode" in core_study and
            "NativeFundedLedger" in core_study and
            "ledger.Apply(e)" in core_study, "NEW_STUDY_MONEY_IN_COMMON_CORE")
    require("new NativeBayesianCommonEpisode()" in replay_study and
            "new NativeCloudResearchParityAdapter()" in replay_study and
            "Same(a,b)" in replay_study, "REPLAY_SAME_EVENT_NATIVE_PARITY")
    require("engine.Advance(eventAtClose,index)" in cloud_adapter and
            "NativeBayesianCommonEpisode engine=new();" in cloud_adapter,
            "CLOUD_ADAPTER_NATIVE_DECISIONS_AND_MONEY")
    require('Compile Include="../Mxm.Cloud/NativeCloudResearchParityAdapter.cs"' in
            replay_project, "SOURCE_IDENTICAL_CLOUD_ADAPTER_IN_REPLAY")
    require("--owner-native-bayes-parity" in
            (ROOT / "src/Mxm.Replay/Program.cs").read_text() and
            "audit_owner_native_bayes_parity" in ci,
            "NEW_NATIVE_ENTRYPOINT_CI")
    print("STRUCTURAL_NATIVE_CSHARP_AUTHORITY_PASSED;"
          " NO_NUMERIC_OR_ECONOMIC_PARITY_CERTIFICATE")


if __name__ == "__main__":
    verify()
