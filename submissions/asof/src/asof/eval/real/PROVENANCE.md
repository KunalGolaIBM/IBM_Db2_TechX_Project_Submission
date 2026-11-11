# Provenance: the US DOT refund rules (real, public-domain regulation)

These files are the official text of 14 CFR 259.5 and parts of 14 CFR part 260 (the US Department of Transportation's airline refund rules), fetched on 10 Nov 2026 from the eCFR point-in-time API (Office of the Federal Register). US federal regulations are in the public domain. Each file is the API's response body byte for byte (the API requires a compressed transfer, `curl --compressed`; the bytes kept are the decompressed body). Their SHA-256 sums are pinned in [tests/test_real_regulation.py](../../../../tests/test_real_regulation.py).

Which parts, and why: the 2024 refund rule (89 FR 32832, 26 Apr 2024, as the files' own source notes cite it) created part 260, which first appears on the eCFR on 2024-06-25 and was corrected and partly renumbered on 2024-08-12 (89 FR 65537). Before it, the binding refund text was 14 CFR 259.5(b)(5), the Customer Service Plan's prompt-refund standard, which the same rule rewrote on 2024-06-25. Part 399 (statements of general policy) and 374.3 (credit-card refunds under Regulation Z) are cited by 259.5 but were not needed for the questions. Dates of each version come from the versions endpoint: `https://www.ecfr.gov/api/versioner/v1/versions/title-14.json?part=259` and `?part=260`.

| File | As of | API URL | Bytes | SHA-256 |
|---|---|---|---|---|
| `ecfr/2023-01-03_259.5.xml` | 2023-01-03 | https://www.ecfr.gov/api/versioner/v1/full/2023-01-03/title-14.xml?part=259&section=259.5 | 3774 | `37506537f05e3f2aaaba06bfaad5f8ee2fef0daa930949ecab7032a66dd1cad2` |
| `ecfr/2024-06-24_259.5.xml` | 2024-06-24 | https://www.ecfr.gov/api/versioner/v1/full/2024-06-24/title-14.xml?part=259&section=259.5 | 3998 | `8e958df95df4d28cd3714de00f8b7b53e9fa40e30a243ae25d494a8dae3c4dd9` |
| `ecfr/2024-07-01_259.5.xml` | 2024-07-01 | https://www.ecfr.gov/api/versioner/v1/full/2024-07-01/title-14.xml?part=259&section=259.5 | 5702 | `99e86d7d4d459e7ac72fbaf51b6c21dfbdaf19d208ecdda29659a9a9d1f36826` |
| `ecfr/2024-07-01_260.6.xml` | 2024-07-01 | https://www.ecfr.gov/api/versioner/v1/full/2024-07-01/title-14.xml?part=260&section=260.6 | 8665 | `f6207742eb2c147b18eeeb568c94529c2d33fead8d61c1de9bb4fdb8143c709c` |
| `ecfr/2024-07-01_260.9.xml` | 2024-07-01 | https://www.ecfr.gov/api/versioner/v1/full/2024-07-01/title-14.xml?part=260&section=260.9 | 956 | `5777ba176b39e6738d76c740acebb08f88fd01e482701fd82c690f7cb99360bd` |
| `ecfr/2025-06-02_259.5.xml` | 2025-06-02 | https://www.ecfr.gov/api/versioner/v1/full/2025-06-02/title-14.xml?part=259&section=259.5 | 5702 | `99e86d7d4d459e7ac72fbaf51b6c21dfbdaf19d208ecdda29659a9a9d1f36826` |
| `ecfr/2025-06-02_260.10.xml` | 2025-06-02 | https://www.ecfr.gov/api/versioner/v1/full/2025-06-02/title-14.xml?part=260&section=260.10 | 1117 | `cefd451a3a150be15086b49d14deb02d2fdee671fa06b68aff5f674d811cf044` |
| `ecfr/2025-06-02_260.6.xml` | 2025-06-02 | https://www.ecfr.gov/api/versioner/v1/full/2025-06-02/title-14.xml?part=260&section=260.6 | 5537 | `0ce631ed94fd1fde2e55e00c203feb3ead15d1a0da83d66f7bbca5d5ff44550b` |
| `ecfr/2026-07-02_259.5.xml` | 2026-07-02 | https://www.ecfr.gov/api/versioner/v1/full/2026-07-02/title-14.xml?part=259&section=259.5 | 5275 | `969ac622e6f8e81a0c4965b0e82b3e205886a0a008de31e69607dc3624c5fea7` |

The PDFs in `pdf/` are made from these files by `text.py` (no word changed; each starts with two lines naming the excerpt and its dates); [tests/test_real_regulation.py](../../../../tests/test_real_regulation.py) checks that intake's reader gets back their words exactly.

| PDF | SHA-256 |
|---|---|
| `pdf/us_dot_refunds_v1.pdf` | `fdcf0a283b0ac6152b1e32492c1100ac302e6c8a230949f1fcfc7e66984c4593` |
| `pdf/us_dot_refunds_v2.pdf` | `bea957371c289258032b0fc77e8310464dfe4b3a0cd2a1c0dd87a7b62a3be9cf` |
| `pdf/us_dot_refunds_v3.pdf` | `8886e19a5881d6e9dec63f5ba1fade7fdd93df0ead798760578a2e7f81291ead` |

This is a demonstration on real regulation, not legal advice. AsOf checks an assistant's claims against the text loaded for a date; it does not interpret the law.
