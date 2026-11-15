# Submission preparation

Submit through https://www.spaceappschallenge.org/2026/ using your team's Project tab. The published deadline is November 15, 2026 at 11:59 PM in the timezone assigned to the team owner's Local Event. Check the time shown on your team page.

## Project description

Flame in Freefall is an English-language research dashboard for exploring NASA microgravity combustion studies. It retrieves source passages, generates cited summaries, ranks investigations by retrieval matches, and compares experimental conditions before conclusions. Missing measurements remain missing. Retrieval scores describe relevance, not material safety or the probability that a conclusion is true.

The public frontend is https://winner-flame-in-freefall.vercel.app/. The backend was reported by the team to be local as of this review. Do not claim that live search works on the public frontend until an external-device test confirms it.

## Sources and attribution

- Official challenge: https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/
- NASA PSI BASS-II, PSI-25: https://psi.nasa.gov/physci/repo/data/investigations/PSI-25
- NASA BASS-II technical report, NASA/TM-20210011385: https://ntrs.nasa.gov/citations/20210011385

These links identify relevant sources. They do not prove that the running database contains them. Before submitting, list the exact documents actually ingested, their URLs, retrieval dates, and any applicable rights notices. Downloaded raw videos are unnecessary for a document-search demonstration unless the implementation analyzes those videos. Source links alone do not replace use of NASA data in the implemented project.

## AI and software disclosure

OpenAI ChatGPT/Codex assisted with code review, translation, documentation, and fixes. Runtime query analysis, evidence grading, answers, and comparisons use the configured OpenAI-compatible model provider; the default provider is DeepSeek. Record the actual provider and model used in your demonstration. BGE-M3 supplies text embeddings. LangGraph coordinates workflow nodes; Milvus supplies hybrid retrieval; SQLAlchemy stores structured records; Unstructured is used for optional hosted document extraction. Dependencies are listed in requirements.txt.

The flame graphic is a concept illustration, not an experiment photograph. Describe any other AI-generated media and tools actually used by your team. Do not claim that every generated statement has been scientifically verified: citation validation checks identifiers against retrieved passages.

## Demo plan: under 30 seconds

1. 0-5 seconds: state the research problem and show the investigation library.
2. 5-14 seconds: ask a research question, show ranked investigations, and open a source passage.
3. 14-24 seconds: compare two populated investigations and show experimental conditions and missing fields.
4. 24-29 seconds: state the intended research use and the current deployment limitation.

Use a recording of the real application. If the backend is local, say so. Alternatively provide no more than seven slides, including title and ending slides. Test the demo and project links in a private browser window without signing in.

## Verified guidance and remaining checks

- Submission route and timezone: https://github.com/nasa/spaceapps/discussions/1916
- Public project links and demo format: https://github.com/nasa/spaceapps/discussions/1991
- NASA data and source attribution: https://github.com/nasa/spaceapps/discussions/1827
- English and AI disclosure checklist: https://github.com/nasa/spaceapps/discussions/1973
- Full submission guide: https://www.spaceappschallenge.org/resources/project-submission-guide/
- Full judging guide: https://www.spaceappschallenge.org/resources/judging-awards-guide/

The full guide pages returned fetch errors during this review. The linked discussions and event page were available. This document does not certify eligibility or predict a judging score. Confirm registration, team membership, final submission status, and local-event requirements on the official site.
