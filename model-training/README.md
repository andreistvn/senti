# SentiNet Thesis Lab: External Data Validation & Annotation Guide

**Classification Paradigm:** Tier-2 Sequence-Based Layer-2 Anomaly Detection  
**Analytical Environment:** Decoupled Host-Based Network Telemetry  
**Experimental Scope:** Layer-2 Address Resolution Protocol (ARP) Mitigation  

---

## 1. Document Purpose

This guide serves as an objective reference manual for independent third-party validators, auditors, and external annotators. It describes the structural schemas, underlying features, and chronological collection sequences of the datasets provided in this hand-off package.

By providing raw, unmanipulated telemetry output alongside public benchmark data, SentiNet ensures absolute experimental transparency, peer reproducibility, and statistical validation integrity.

---

## 2. Hand-off Package Inventory

This validation bundle contains the following items:

1. **`training_data2.csv`** — SentiNet Primary Custom Dataset. Contains **4,332 rows** of chronologically ordered, **5-second** sliding-window network feature vectors.
2. **`kaggle_raw.csv`** — External Public Benchmark. A raw, unedited network flow log structured using bidirectional Netflow (NFStream) formats.
3. **`README.md`** — This structural guide, feature legend, and mapping taxonomy.

---

## 3. SentiNet Core Dataset Specification (`training_data2.csv`)

The data records in `training_data2.csv` are calculated over **non-overlapping 5-second observation windows** from a live virtual network interface bridged to a physical TP-Link Deco Layer-2 broadcast domain.

### Sliding-Window Feature Legend

The dataset utilizes an **8-dimensional** numerical feature space mapped to a classification target label:

| Column Index | Attribute Identifier | Data Type | Physical/Mathematical Description |
| :---: | :--- | :--- | :--- |
| **0** | `arp_request_rate` | Float64 | Average rate of ARP request frames (Opcode 1) captured per second during the window: **Requests / 5.0s**. |
| **1** | `arp_reply_rate` | Float64 | Average rate of ARP reply frames (Opcode 2) captured per second during the window: **Replies / 5.0s**. |
| **2** | `req_to_reply_ratio` | Float64 | Mathematical ratio of request frames to reply frames inside the window: **Requests / max(1, Replies)**. *(Clamped at a minimum divisor of 1 to prevent zero-division exceptions).* |
| **3** | `unique_ip_per_mac` | Int64 | The maximum number of unique IP addresses mapped to a single physical hardware MAC address captured within the window. |
| **4** | `iat_mean` | Float64 | The mean Packet Inter-Arrival Time (IAT) calculated over all sequential packets within the active window: $\frac{1}{N-1} \sum_{i=1}^{N-1} (t_{i+1} - t_i)$, measured in seconds. |
| **5** | `iat_variance` | Float64 | The statistical sample variance of the Packet Inter-Arrival Times (IAT) within the active window, measured in **seconds²**. Exposes high-frequency robotic scripts. |
| **6** | `packet_burstiness` | Float64 | The sample variance of packet counts computed across five discrete 1-second sub-intervals inside the 5-second window. Differentiates smooth automated streams from erratic human-triggered traffic. |
| **7** | `gratuitous_arp_count`| Int64 | The total count of gratuitous ARP frames intercepted where the source IP identity matches the destination IP identity: **IP_src == IP_dst**. |
| **8** | `label` | String | Ground-truth behavioral class branding: `normal` or `arp_spoofing`. |

### Chronological Block Boundaries
Because sequence-based telemetry contains historical dependencies, a standard randomized cross-validation split (e.g., shuffling rows out of order) will cause structural data leakage. To perform a valid temporal split (**80% train / 20% test**), the validator must group and partition rows by their sequential blocks:

* **Rows 0 to 1,808 (Block 1):** `normal`
  * **Description:** Benign baseline network activity. Generated over **15** sequential **10-minute** sessions with background traffic scripts mimicking typical user activity (web requests, cache flushes, local subnet sweeps).
* **Rows 1,809 to 3,008 (Block 2):** `arp_spoofing`
  * **Description:** Low-velocity, targeted ARP spoofing. Generated over **10** sequential sessions where an attack machine injected malicious unicast replies targeting the victim interface at a rate of **100** Packets Per Second (PPS).
* **Rows 3,009 to 4,331 (Block 3):** `arp_spoofing`
  * **Description:** High-velocity ARP flooding. Generated over **10** sequential sessions where an attack machine flooded the target interface with randomized MAC signatures using kernel-throttled `tcpreplay` injection at **1,000** PPS.

---

## 4. Public Benchmark Dataset Specification (`kaggle_raw.csv`)

To satisfy comparative analysis requirements, a raw flow-based external dataset (`kaggle_raw.csv`) is included. This dataset presents network activity captured using different telemetry architectures.

### Structural Variations & Comparative Guidance
* **Telemetry Model:** Unlike SentiNet’s 5-second localized sliding windows, the Kaggle benchmark is a **flow-based** Netflow/NFStream matrix. Rather than recording fixed temporal windows, it tracks entire bidirectional communication conversations.
* **Target Protocols:** While SentiNet focuses exclusively on Layer-2 ARP frames, the public benchmark captures a wide variety of Layer-4 IP protocols (TCP, UDP, IGMP) and includes feature columns tracking flags.

### Feature Mapping Taxonomy for Validators
If executing a cross-validation audit or schema translation, the following 9 source columns should be retained and mapped to match the SentiNet structural framework:

| Target SentiNet Feature | Source Kaggle Header | Analytical Conversion Logic |
| :--- | :--- | :--- |
| `arp_request_rate` | `src2dst_packets` & `src2dst_duration_ms` | Outward flow packet velocity: $\text{packets} / (\text{duration\_ms} / 1000)$ |
| `arp_reply_rate` | `dst2src_packets` & `dst2src_duration_ms` | Return flow packet velocity: $\text{packets} / (\text{duration\_ms} / 1000)$ |
| `req_to_reply_ratio` | `src2dst_packets` & `dst2src_packets` | $\text{src2dst\_packets} / \max(1, \text{dst2src\_packets})$ |
| `unique_ip_per_mac` | `Label` | Dynamic placeholder ($1$ for `normal`, $2$ for anomalies) |
| `iat_mean` | `bidirectional_mean_piat_ms` | Convert mean packet interval to seconds: $\text{ms} / 1000$ |
| `iat_variance` | `bidirectional_stddev_piat_ms` | Convert standard deviation to variance: $(\text{stddev\_ms} / 1000)^2$ |
| `packet_burstiness` | `bidirectional_stddev_ps` | Maps packet size standard deviation to model variance arrays |
| `gratuitous_arp_count`| `dst_ip` | Flags multicast targets (e.g., destinations starting with `224.`) |
| **Target Label** | **`Label`** | Pass-through: `normal` $\rightarrow$ `normal`, others $\rightarrow$ `arp_spoofing` |

---

## 5. Ground-Truth Integrity & Preprocessing Notes

During the generation of the primary dataset, the following data collection controls were strictly enforced to ensure scientific validity:

1. **Temporal Labeling Isolation:** Data points were assigned malicious labels strictly if an active attack program was actively injecting frames on the local Layer-2 domain during the active capture window.
2. **Transition Window Filtering:** To guarantee class label purity and eliminate boundary noise, any 5-second sampling window that spanned the exact split second an attack sequence was initiated or halted was discarded. This prevents fuzzy intermediate states from skewing model evaluation.
3. **Unicast Stealth Signatures:** Malicious packets were directed as unicast frames to the victim interface, rather than broadcast floods across the entire subnet. This reflects stealthy, modern penetration techniques and explains why local features (such as `iat_variance` and `req_to_reply_ratio`) show significant shifts while broader network-wide counts remain unaffected.