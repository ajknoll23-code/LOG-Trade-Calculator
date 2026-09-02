# Young RB Continuous-Age Architecture Audit

**Status:** research-only; no production values changed.

## Architecture being tested

Replace integer-age step changes with exact fractional age. Preserve the current ordinary-RB pre/post-peak endpoints, but evaluate them continuously. Replace the elite young-RB override with a monotone premium taper from the deployed age-21 anchor to 1.0 at age 25.

- Birthday events audited: **48**

## Structural birthday discontinuity

| Candidate | Median abs exact birthday jump | Max abs exact birthday jump |
|---|---:|---:|
| deployed_integer | +7.6% | +40.9% |
| continuous_linear | +0.0% | +0.1% |
| continuous_smoothstep | +0.0% | +0.1% |
| continuous_quadratic | +0.0% | +0.1% |

## All usable events

- N: **48**

| Candidate | MAE | Median abs error | Median bias | Median predicted change | Bootstrap P(improves vs deployed) |
|---|---:|---:|---:|---:|---:|
| deployed_integer | +21.9% | +16.4% | +8.9% | +0.0% | n/a |
| continuous_linear | +22.1% | +17.7% | +2.4% | +0.0% | 44.8% |
| continuous_smoothstep | +22.1% | +17.7% | +2.4% | +0.0% | 46.2% |
| continuous_quadratic | +22.1% | +17.7% | +2.4% | +0.0% | 47.5% |

## Meaningful-production events

- N: **26**

| Candidate | MAE | Median abs error | Median bias | Median predicted change | Bootstrap P(improves vs deployed) |
|---|---:|---:|---:|---:|---:|
| deployed_integer | +17.6% | +13.3% | +8.9% | +0.0% | n/a |
| continuous_linear | +16.3% | +11.7% | +1.9% | -0.4% | 84.0% |
| continuous_smoothstep | +16.3% | +11.7% | +1.9% | -0.4% | 81.5% |
| continuous_quadratic | +16.2% | +11.7% | +1.9% | -0.4% | 84.6% |

## High-production events

- N: **15**

| Candidate | MAE | Median abs error | Median bias | Median predicted change | Bootstrap P(improves vs deployed) |
|---|---:|---:|---:|---:|---:|
| deployed_integer | +15.5% | +9.5% | +4.3% | +0.0% | n/a |
| continuous_linear | +12.0% | +4.1% | +1.2% | -0.4% | 97.9% |
| continuous_smoothstep | +12.0% | +4.1% | +1.2% | -0.4% | 98.0% |
| continuous_quadratic | +11.9% | +4.1% | +1.2% | -0.4% | 98.7% |

## Elite-role events

- N: **6**

| Candidate | MAE | Median abs error | Median bias | Median predicted change | Bootstrap P(improves vs deployed) |
|---|---:|---:|---:|---:|---:|
| deployed_integer | +17.5% | +8.9% | -1.3% | +1.1% | n/a |
| continuous_linear | +15.9% | +5.4% | -1.3% | -1.0% | 70.5% |
| continuous_smoothstep | +16.0% | +5.4% | -1.5% | -1.1% | 69.3% |
| continuous_quadratic | +15.5% | +4.9% | -0.8% | -0.7% | 72.1% |

## By birthday transition

### 21->22

- N: **8**

| Candidate | MAE | Median abs error | Median bias | Median predicted change | Bootstrap P(improves vs deployed) |
|---|---:|---:|---:|---:|---:|
| deployed_integer | +27.3% | +17.5% | +8.4% | +37.9% | n/a |
| continuous_linear | +28.5% | +21.0% | -7.0% | +2.7% | 46.2% |
| continuous_smoothstep | +28.5% | +21.0% | -7.0% | +2.7% | 45.6% |
| continuous_quadratic | +28.4% | +21.0% | -7.0% | +2.7% | 46.3% |

### 22->23

- N: **11**

| Candidate | MAE | Median abs error | Median bias | Median predicted change | Bootstrap P(improves vs deployed) |
|---|---:|---:|---:|---:|---:|
| deployed_integer | +28.3% | +16.0% | +10.5% | +27.0% | n/a |
| continuous_linear | +27.2% | +17.8% | -13.6% | +1.1% | 56.3% |
| continuous_smoothstep | +27.2% | +17.8% | -13.6% | +1.1% | 55.8% |
| continuous_quadratic | +27.2% | +17.8% | -13.6% | +1.1% | 56.9% |

### 23->24

- N: **12**

| Candidate | MAE | Median abs error | Median bias | Median predicted change | Bootstrap P(improves vs deployed) |
|---|---:|---:|---:|---:|---:|
| deployed_integer | +11.5% | +8.9% | +4.1% | +0.0% | n/a |
| continuous_linear | +11.1% | +4.1% | +3.1% | +0.0% | 61.5% |
| continuous_smoothstep | +11.1% | +4.1% | +3.1% | +0.0% | 61.1% |
| continuous_quadratic | +11.0% | +4.1% | +3.1% | +0.0% | 60.6% |

### 24->25

- N: **9**

| Candidate | MAE | Median abs error | Median bias | Median predicted change | Bootstrap P(improves vs deployed) |
|---|---:|---:|---:|---:|---:|
| deployed_integer | +19.3% | +17.3% | +14.3% | +0.0% | n/a |
| continuous_linear | +19.3% | +17.7% | +13.9% | -0.4% | 63.0% |
| continuous_smoothstep | +19.3% | +17.7% | +13.9% | -0.4% | 64.6% |
| continuous_quadratic | +19.3% | +17.7% | +13.9% | -0.4% | 63.9% |

### 25->26

- N: **8**

| Candidate | MAE | Median abs error | Median bias | Median predicted change | Bootstrap P(improves vs deployed) |
|---|---:|---:|---:|---:|---:|
| deployed_integer | +26.4% | +20.5% | +17.3% | -7.6% | n/a |
| continuous_linear | +28.5% | +27.3% | +24.1% | -0.8% | 13.7% |
| continuous_smoothstep | +28.5% | +27.3% | +24.1% | -0.8% | 14.6% |
| continuous_quadratic | +28.5% | +27.3% | +24.1% | -0.8% | 13.3% |

## Interpretation boundary

Observed market changes remain confounded by football news and changing historical roles. This audit is strongest as a structural discontinuity test. Paired error improvement is supporting evidence, not causal proof of the exact age curve.

A production candidate should only advance if it eliminates the structural birthday jump and does not materially worsen paired external-event error in the meaningful/high-production cohorts.
