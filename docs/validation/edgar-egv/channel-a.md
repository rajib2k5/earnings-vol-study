# Channel A (documentation audit), EDGAR timing claims E1-E8

Retrieval date for every record: 2026-11-09. Written before reading any Channel B output. No code run, no data file fetched,
no request sent to data.sec.gov, no contact detail sent to any site.

Retrieval notes:
- sec.gov HTML pages were read through WebFetch, which summarises with a small model; quotes marked (extract) are that tool's
  extraction, not my own reading of raw HTML. PDFs (Form 8-K, Filer Manual Vol. II) I read myself as page images.
- No sec.gov page refused fetching. The EDGAR Filer Manual Vol. II v78 is dated September 14, 2026.
- A "how to determine filing date" SEC page I guessed returned 404; I did not retry it and used 17 CFR 232.13 instead.
- SEC's API page and the fair-access pages carry the dates stated below; none document acceptanceDateTime directly.

---

claim_id:    E1
verdict:     UNVERIFIABLE
source:      https://www.sec.gov/search-filings/edgar-application-programming-interfaces
source_tier: 1
version:     page banner June 6, 2024; "Last Reviewed or Updated" April 8, 2025
quote:       (extract) main data is in a "compact columnar data array", at least one year or up to 1,000 recent filings
retrieved:   2026-11-09
note:        The page documents the URL pattern CIK##########.json (ten digits with leading zeros) and a columnar structure, but names
             none of form, items, accessionNumber, acceptanceDateTime, and does not say "filings.recent". The array names are
             undocumented here; the other channel must check them against a real response.

claim_id:    E2
verdict:     UNVERIFIABLE
source:      https://www.sec.gov/search-filings/edgar-application-programming-interfaces
source_tier: 1
version:     June 6, 2024 / reviewed April 8, 2025
quote:       (extract) "If the entity has additional filings, files will contain an array of additional JSON files and the date range"
retrieved:   2026-11-09
note:        Documents that an additional-files array exists with date ranges. It does not name the files, state that they are served at
             data.sec.gov/submissions/<name>, or say they carry the same arrays as filings.recent.

claim_id:    E3
verdict:     UNVERIFIABLE (SEC is silent on the time zone of acceptanceDateTime in the submissions API)
source:      https://www.sec.gov/about/webmaster-frequently-asked-questions ; API page above
source_tier: 1
version:     webmaster FAQ dated May 19, 2021, last reviewed Aug. 23, 2024
quote:       (extract) "Acceptance Time: Time (EST) at which the submission was accepted by EDGAR. Format is HHMMSS"
retrieved:   2026-11-09
note:        What SEC says exactly: (a) the submissions API page gives no time zone for acceptanceDateTime and never mentions "Z" or UTC; its
             only ET reference concerns bulk ZIP republishing at "approximately 3:00 a.m. ET". (b) The FAQ describes the acceptance time in the
             complete-submission-text header (<ACCEPTANCE-DATETIME>20190311165759) as "EST", and never uses the term acceptanceDateTime.
             The FAQ says nothing about EDT or UTC. So the only SEC statement about acceptance-time zone points to Eastern, not UTC, for
             the header field. Whether the JSON field is the same instant re-expressed with "Z" is undocumented. A search snippet mentioned a
             separate EDGAR submission-status API returning RFC3339 timestamps; that is a different API and I did not read it.
             Do not accept E3 on documentation alone; it needs an empirical check against a filing whose header time is known.

claim_id:    E4
verdict:     UNVERIFIABLE
source:      17 CFR 232.13 via eCFR https://www.ecfr.gov/ (section 232.13(a)); webmaster FAQ above
source_tier: 1
version:     eCFR current as retrieved
quote:       (extract) filings "commencing after 5:30 p.m." are deemed filed the next business day; Eastern Standard or Daylight time "whichever is currently in effect"
retrieved:   2026-11-09
note:        Documented: the 5:30 p.m. Eastern cutoff and next-business-day filing date (with 10 p.m. exceptions in (a)(3)-(a)(4) for certain
             filings; Form 8-K is not named in what I read, so check which cutoff applies to 8-K). Documented: acceptance time is the time
             "accepted by EDGAR". Not documented: that the API's acceptanceDateTime keeps the true acceptance time, rather than a
             filing-date-adjusted time, for after-cutoff filings. The two quantities (filing date vs acceptance time) are described separately,
             which is consistent with E4 but is not a statement of it.

claim_id:    E5
verdict:     UNVERIFIABLE
source:      https://www.sec.gov/search-filings/edgar-application-programming-interfaces
source_tier: 1
version:     June 6, 2024 / reviewed April 8, 2025
quote:       (none; the page does not mention the items field)
retrieved:   2026-11-09
note:        No SEC page I read documents the format of `items`. The string "2.02,9.01" is an empirical matter.

claim_id:    E6
verdict:     CONFIRMED
source:      https://www.sec.gov/files/form8-k.pdf (read pages 3 and 14-15 myself)
source_tier: 1
version:     Form 8-K, SEC 873 (02-25), OMB expiry Nov 30, 2027
quote:       "Item 2.02 Results of Operations and Financial Condition." ... "include the text of that announcement or release as an exhibit."
retrieved:   2026-11-09
note:        Item 2.02(a) covers a public announcement or release disclosing material non-public information on results of operations or
             financial condition for a completed quarterly or annual period. General Instruction B.2 (p.3): information "furnished pursuant
             to Item 2.02" is not deemed "filed" for Exchange Act Section 18, which supports the word "furnishes". Item 2.02 is
             also used for any such results release, not only earnings releases in a narrow sense; instruction 1 says it is triggered by
             disclosure about "a completed fiscal year or quarter".

claim_id:    E7
verdict:     CONFIRMED (EDGAR clause only; the NYSE clause was not audited)
source:      https://www.sec.gov/submit-filings/filer-support-resources/edgar-calendar
source_tier: 1
version:     banner June 5, 2024; "Last Reviewed or Updated" Oct. 20, 2026; table "Federal Holidays in 2026"
quote:       (extract) "The EDGAR system will not receive, process, or accept filings in observance of the following federal holidays."
retrieved:   2026-11-09
note:        The 2026 table lists Columbus Day (Monday, October 12) and Veterans Day (Wednesday, November 11) among those holidays.
             Applies to 2026 as published; earlier years in the study span (2020-2025) are not covered by this page and need the same
             page's prior-year calendars or the Filer Manual of those years. The statement that NYSE is open on those days is not an
             SEC claim and I did not retrieve an NYSE primary source. The Filer Manual Vol. II v78 (p.2-6) states hours "Monday through
             Friday, from 6:00 A.M. to 10:00 P.M., Eastern Time", unavailable after 10:00 P.M.; it does not list holidays in the pages I read.

claim_id:    E8
verdict:     CONFIRMED for the rate; the User-Agent clause is supported by a sample but the word "requires" is not verified verbatim
source:      https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data ; https://www.sec.gov/about/webmaster-frequently-asked-questions
source_tier: 1
version:     accessing-edgar-data: March 23, 2021, reviewed June 26, 2024; webmaster FAQ: May 19, 2021, reviewed Aug. 23, 2024
quote:       (extract) "Current max request rate: 10 requests/second." ; webmaster FAQ: "our current maximum access rate is 10 requests per second."
retrieved:   2026-11-09
note:        Both pages say to declare a user agent in request headers; the sample is a company name plus an admin contact email
             ("Sample Company Name AdminContact@<sample company domain>.com"). The tool paraphrased the instruction as "asks"; whether the
             page says "must" is unverified. The cap is a "maximum", so "at most 10" matches. Both pages reviewed 2024, so 2026 limits
             should be rechecked on the live page by whoever acts on this.
