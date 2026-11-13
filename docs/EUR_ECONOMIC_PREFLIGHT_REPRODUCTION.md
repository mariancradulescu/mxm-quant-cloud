# PR #265 original reproduction evidence

The original local execution used Python 3.12 and NumPy 2.3.5. The
preserved input was `MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip`,
SHA-256 `09d999a595436de73c5edbb3d4a84002dc8b8779dc94393473d43afe1c3d9259`.
It is the original Pepperstone development archive whose manifest and
account commitment are checked by the equity-source loader.

Original local verification from the repository root, with the archive in
the adjacent development-sources directory:

```sh
python -m py_compile research/eur_economic_preflight.py
python -m research.eur_economic_preflight ../development_sources/MXM_RESEARCH_CORE_V3_SELECTED_M5_DEVELOPMENT.zip /tmp/mxm-eur-preflight-verify.json
cmp docs/EUR_ECONOMIC_PREFLIGHT_RESULT.json /tmp/mxm-eur-preflight-verify.json
sha256sum docs/EUR_ECONOMIC_PREFLIGHT_RESULT.json
```

The original tool execution reported exit status 0 for the reproduction
and comparison. The retained working copy and the published JSON still
compare byte for byte. Both have SHA-256
`8dfb9f289f371607a66d96700ae33d3afc5f4ca151143c0d37a6bb5e954ddad1`.
The temporary verification output is no longer retained. This addendum
records the original execution and current integrity checks, with no new
replay. Actions [43395941270](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43395941270)
and [43396177215](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43396177215)
were general CI. They provide no independent reproduction of this module.
