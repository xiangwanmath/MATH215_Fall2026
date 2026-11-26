# **Project Description**
## What is Archelous?
tldr: perplexity but free and the user has control over the entire stack

1.  Archelous is a academic tool that   combines the accuracy of a search engine with the scope of a large language model.
2. Archelous takes a user query, turns it into a web search, then passes the information from the desired websites along with the user query to a locally run large language model. The model then takes the user query and the scraped information (all in plain text) to synthesize a repsonse to the query based on the information given.
3. Archelous is designed to be as accurate as possible, and therefore has a specific list of website that it is allowed to access for data, as well as strict guardrails on the local large language model to only use the information provided to determine an answer to the user query, instead of leaning on it's own training data or hallucinating.
---
## What's to come?
1. Custom trained and fine-tuned large language models (or other machine learning algorithims) to eliminate hallucination and make certain that
2. A possible re-write of the entire codebase to faster more comprehensive languages, current front runners include zig, rust, and c++
3. A clean, stylish ui and ux (a frontend so it isn't just a terminal application)
4. More debugging and optimization for faster, more accurate, and more consistent responses. Aiming to eliminate the "I do not have enought information to respond" output to a user query
---
### - Veryovkin-Schmeling Labs 2026
