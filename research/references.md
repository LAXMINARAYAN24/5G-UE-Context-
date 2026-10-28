# Reference register

Checked 7 October 2026. Access limitations are recorded to prevent overstating the review.

1. J. Sid-Otmane, S. Imadali, F. Martelli, M. Shapiro, **Data Consistency in the 5G Specification**, ICIN 2020, pp. 110–117. DOI: [10.1109/ICIN48450.2020.9059408](https://doi.org/10.1109/ICIN48450.2020.9059408). [Publisher](https://ieeexplore.ieee.org/document/9059408/), [author manuscript](https://pages.lip6.fr/Marc.Shapiro/papers/Data_Consistency_in_the_5G_Specification.pdf). Conceptual reference selected for this implementation; publisher abstract and indexed manuscript introduction accessible. Full PDF retrieval failed and HAL blocked access. No full-text review or replication is claimed.
2. **Anomaly Detection using a Semi-Supervised Deep Learning Model on Open 5G Core Metrics during User-Equipment Registration**, IEEE CSCN 2023. DOI: [10.1109/CSCN60443.2023.10453203](https://doi.org/10.1109/CSCN60443.2023.10453203). [Publisher](https://ieeexplore.ieee.org/document/10453203/). Publisher abstract verified; full paper and data not retrieved.
3. **A Framework for AI-Based Large-Scale Time-Series Anomaly Detection in 5G Core Networks**, IEEE ICTC 2025. DOI: [10.1109/ICTC66702.2025.11388910](https://doi.org/10.1109/ICTC66702.2025.11388910). [Publisher](https://ieeexplore.ieee.org/abstract/document/11388910). Publisher abstract verified; full paper and operator data not retrieved. The conference was in 2025 and IEEE added the record in February 2026.
4. **3GPP TS 23.502 V16.18.0**, Procedures for the 5G System, sections 4.3.2, 4.3.3, 4.3.4. [ETSI PDF](https://www.etsi.org/deliver/etsi_ts/123500_123599/123502/16.18.00_60/ts_123502v161800p.pdf). Procedure references for establishment, modification and release; the implementation abstracts them.
5. **3GPP TS 38.413 V16.5.0**, NG Application Protocol, sections 8.2.1, 8.2.2, 8.2.3. [ETSI PDF](https://www.etsi.org/deliver/etsi_ts/138400_138499/138413/16.05.00_60/ts_138413v160500p.pdf). Resource setup, release and modification references. No NGAP encoding is implemented.
6. **3GPP TS 38.300 V16.2.0**, NR and NG-RAN Overall Description. [ETSI PDF](https://www.etsi.org/deliver/etsi_ts/138300_138399/138300/16.02.00_60/ts_138300v160200p.pdf). Access state and mobility background; the mobility example is a local-cell negative control only.
7. **3GPP TS 38.412 V16.0.0**, NG signalling transport, sections 4.1 and 7. [ETSI PDF](https://www.etsi.org/deliver/etsi_ts/138400_138499/138412/16.00.00_60/ts_138412v160000p.pdf). Reliable NGAP signaling over SCTP. This prevents interpreting ordinary packet loss as silent permanent loss of reliably delivered signaling.
8. [SimPy official documentation](https://simpy.readthedocs.io/en/latest/index.html), discrete-event framework used for virtual-time experiments.
9. [Streamlit official documentation](https://docs.streamlit.io/), demonstration interface.
10. [uv official documentation](https://docs.astral.sh/uv/), dependency management and locked environments.

The comparison describes published scope. Inferences about what these scopes do not
cover are project positioning, not purported quotations from the papers' limitation sections.
