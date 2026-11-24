"""Verify GitHub's authenticated review records for the CPE1 recovery."""
import json
import re
import sys

OWNER_ACCOUNT_ID = 322088485
OWNER_REVIEW_ENVIRONMENT = "cpe1-recovery-1-owner-review"


def verify_independent_audit(comment, auditor_id, issue_url, reviewed_head, ci_run):
    # This ID is set in GitHub repository settings by the OWNER, outside Git.
    if not re.fullmatch(r"[1-9][0-9]{0,19}", auditor_id) or int(auditor_id) == OWNER_ACCOUNT_ID:
        raise ValueError("CPE1_REGISTER_DISTINCT_INDEPENDENT_AUDITOR")
    user = comment.get("user") or {}
    created = comment.get("created_at")
    approval = f"CPE1_TECHNICAL_RECOVERY_1_INDEPENDENT_APPROVAL {reviewed_head} {ci_run}"
    if (user.get("id") != int(auditor_id) or user.get("type") != "User" or
            comment.get("issue_url") != issue_url or not created or created != comment.get("updated_at") or
            approval not in (comment.get("body") or "").splitlines()):
        raise ValueError("CPE1_INDEPENDENT_AUDIT_IDENTITY_OR_SCOPE_INVALID")


def verify_owner_review(reviews):
    # The run-scoped review history supplies the authenticated account.
    # An automatically created environment has no approval in that history.
    for review in reviews:
        user = review.get("user") or {}
        if (review.get("state") == "approved" and user.get("type") == "User" and
                user.get("id") == OWNER_ACCOUNT_ID and
                any(env.get("name") == OWNER_REVIEW_ENVIRONMENT for env in review.get("environments", []))):
            return
    raise ValueError("CPE1_EXPLICIT_OWNER_DEPLOYMENT_REVIEW_REQUIRED")


def main():
    match sys.argv[1:]:
        case ["audit", auditor, issue, head, ci]:
            verify_independent_audit(json.load(sys.stdin), auditor, issue, head, ci)
        case ["owner"]:
            verify_owner_review(json.load(sys.stdin))
        case _:
            raise SystemExit("CPE1_INVALID_AUTHORITY_CHECK")


if __name__ == "__main__":
    main()
