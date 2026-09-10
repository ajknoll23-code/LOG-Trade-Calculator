# Package Adjustment — OOS Monitor Externalization

**No production or workflow change performed.**

The exact Python implementation embedded in the permanent V1.5 OOS workflow has been copied into a normal tracked validator script. This preserves the current monitor implementation while removing the need for future formula changes to edit a giant inline workflow.

- Source workflow SHA-256: `2169b24b988d2521e5e8a0445220f6f335591e7b6a00a14ecb760f2fd183e0de`
- Externalized script SHA-256: `2810f249b3528de5acddcde991d1d4ed3e11d6ad570d38b8ad4ae7e7b33ecdbd`
- Current production revision remains `v1.5-audit-step6-scope-ui-idp`.
- Permanent workflow is still byte-identical at this step.

Next: add a V1.5/V1.6 dispatcher and replace the permanent workflow manually with a thin runner.
