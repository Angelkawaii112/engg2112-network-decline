# E4 — Is the Universal Outdoor Mobile Obligation enough for the E1 gaps?

**Policy status checked:** 25 October 2026. The Minister's 16 October 2026 release says the UOMO legislation has passed Parliament and sets a planned start of 1 December 2027, subject to market developments. Treat this as a future obligation in this study until the final Act, Royal Assent and operative standards are checked against the Federal Register of Legislation.

**E1 results snapshot:** The team-reported run uses ACCC 4G outdoor map layers with reference date 31 January 2026. See [E1 results and method notes](E1_results.md). E3 has not yet been run; no Ookla pre/post result is used here.

## Policy question

E4 asks whether the future outdoor SMS/voice baseline addresses the needs measured in E1. It does not treat “national satellite reach” as delivered service, and it separates a policy target from capability already available to a customer.

## Assessment

### What the policy is intended to provide

The Government describes the UOMO as requiring Telstra, Optus and TPG to provide SMS and voice coverage outdoors across Australia, using a mix of existing towers and LEO Direct-to-Device satellites. It says the obligation will start on 1 December 2027, subject to market developments, and that the law enables the Minister to set service standards, benchmarks and rules.

The October 2026 ACCC discussion paper says D2D messaging services are emerging but D2D voice services are not currently available. It also describes D2D as nascent, with future technical capability, commercial viability and adoption uncertain. Therefore, the obligation is a policy commitment whose technical implementation and reliability still need evidence.

### Does this meet current E1 needs?

- **Text:** Partly addressed in the interim. Telstra already offers satellite messaging, but it requires a compatible device, plan, outdoor use and clear sky, is intermittent, and is not an emergency service. It is not equivalent to a full terrestrial mobile service.
- **Ordinary mobile voice:** Not currently addressed by D2D retail services as of the evidence date. Government LEO voice tests establish that a fixed voice service over Starlink broadband can work well at tested locations; they do not prove that a phone can make a direct satellite voice call while on a road.
- **Emergency calling (000):** The Government describes the policy as supporting calls for help in emergencies. However, Telstra's current D2D messaging service expressly cannot call or text Triple Zero. E4 must verify the final legislation and subsequent standards for emergency-call access, routing, location, power resilience, call completion, and outage handling. Do not infer those details from a general policy statement.
- **Mobile broadband/data:** The described UOMO baseline is voice and SMS. It does not promise full mobile broadband. Telstra's D2D selected-app feature is limited low-bandwidth data, not general internet access.
- **Population and roads:** The team-reported E1 summary identifies 22,611 modelled residents (0.27% of the NSW population) and 3,572 km of State/Regional roads (8.7% of the selected road network) in the mapped gap. Population is modelled from a 1 km grid, and the road layer excludes local roads. These figures describe exposure, not current UOMO service availability.

## E1-based adequacy test

| E1 measure | NSW result |
|---|---:|
| Area outside all three predicted 4G outdoor coverage maps | 248,000 km² (31% of NSW) |
| Modelled residents in the map gap | 22,611 (0.27% of NSW population) |
| State/Regional road length in the map gap | 3,572 km (8.7% of selected road network) |
| Geocoded hospitals in the map gap | 4 of 382 |
| Very Remote residents estimated in the gap | 14.5% |
| Remote/Outer Regional residents estimated in the gap | 3.5% |

The main pattern is a spatial mismatch: the map gap covers a large share of land and a material share of selected roads, while containing a small share of NSW's modelled population. This supports treating the gap as an outdoor route-continuity problem as well as a local access issue; it does not mean that residential impacts are absent. Four geocoded hospital locations are potential access exposures in the mapped gap. The supplied result groups Remote and Outer Regional at 3.5%; verify the category denominator against population_by_remoteness.csv before publishing separate category claims.

Interpret the policy results in three stages:

1. **Current adequacy:** D2D SMS provides a limited messaging layer, but no currently verified D2D voice layer. Fixed LEO broadband/fixed voice can help eligible premises but does not cover the road user.
2. **Committed future scope:** UOMO aims to require outdoor voice and SMS by 1 December 2027. This would address a more important baseline than today's SMS-only D2D offering, if it is implemented with reliable service and verified emergency calling.
3. **Residual gap:** Full mobile data, indoor access, continuous availability, handset compatibility, and actual service quality remain separate questions. E1's geographic gap estimate cannot be “subtracted” using a broad D2D footprint claim without published service polygons and coverage-performance evidence.

This is a qualitative adequacy finding. It does not subtract population or road kilometres using an approximate satellite footprint. The team's Optus–TPG MOCN sensitivity check reportedly produced the same E1 summary when its shared-network map was included; treat that as a robustness check, not as an extra operator or additional area of coverage. E3 has not been run, so it cannot be used as evidence of a Starlink-associated speed change or satellite benefit.

The policy can therefore be described as **potentially sufficient for a minimum outdoor voice/SMS obligation if implementation and emergency standards are delivered**, but **not yet demonstrated as an operational replacement for terrestrial coverage**, and **not a promise of broadband or a full mobile-service experience**.

## Evidence and status notes

- The UOMO passed Parliament according to the Minister's 16 October 2026 announcement; this draft records the announcement, not an independently verified Royal Assent date.
- The planned commencement date is 1 December 2027, subject to market developments, according to that same release.
- The Parliamentary Library Bills Digest explains the original bill's intended SMS/voice scope and default commencement provisions. It predates passage and should not be treated as the final Act.
- Keep a status-check date in any final report. Replace this note with the final Act and any instruments/standards once they are published.
- The trial's average MOS result is evidence for fixed voice over a LEO broadband path. The policy concerns outdoor mobile voice and SMS; they are related but distinct outcomes.

## Sources

- [Minister for Communications — UOMO passed Parliament and planned commencement](https://minister.infrastructure.gov.au/wells/media-release/ensuring-better-mobile-coverage-all-australians) (16 October 2026)
- [ACCC — Mobile services inquiry discussion paper, October 2026](https://www.accc.gov.au/system/files/mobile-services-inquiry-discussion-paper-october-2026.pdf?download=y) (D2D status, voice availability and limitations)
- [Parliamentary Library — Bills Digest for the UOMO Bill](https://www.aph.gov.au/Parliamentary_Business/Bills_Legislation/bd/bd2526/26bd039) (bill scope and original intended start date)
- [Australian Government — Trials of voice services](https://www.infrastructure.gov.au/media-communications/modernising-universal-telecommunications-services/trials-voice-services)
- [Telstra — Satellite service limitations and Triple Zero support](https://www.telstra.com.au/support/mobiles-devices/satellite-to-mobile)
- [ACCC — 2026 Mobile Infrastructure Report](https://www.accc.gov.au/by-industry/telecommunications-and-internet/mobile-services-regulation/mobile-infrastructure-report/mobile-infrastructure-report-2026)

