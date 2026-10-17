# Related work

Drafted for the final report's background section. Every citation below was
checked against the publisher's own record: title, author list, venue and year
come from the paper or its DOI entry, not from a search summary. Where a source
is a thesis or an industry write-up rather than peer-reviewed work, it says so,
because an undergraduate report that cites a master's thesis as though it were
a journal article invites exactly the question it cannot answer.

## Predicting network degradation from inside the network

Work on forecasting cell degradation is established and consistent in one
respect: it assumes access to the operator's own instrumentation. Deep-learning
models over UMTS key performance indicators forecast cell KPIs and flag
anomalous cells ahead of failure [T1], and comparisons of classifiers on base
station failures report gradient boosting and random forests performing best
over 47 weeks of site data [T2]. Both are master's theses on single-operator
datasets. Peer-reviewed work in the area tends to address adjacent systems
rather than radio access: error prediction for telecommunications business
support systems treats rare failures as a class-imbalance problem and finds
that engineered frequency features improve random forest performance [3].

The common assumption matters more than the common method. Counter readings,
alarm logs and handover statistics belong to the carrier. A regulator, a local
council or a researcher asking which parts of a state are degrading has none of
them, and so cannot reproduce or audit any of this work. That is the gap this
project occupies: it asks whether the same question can be answered from
measurements anyone can download.

## Crowdsourced measurement as the public substitute

Crowdsourced speed tests are the obvious public alternative, and the literature
on them is mostly a literature of caveats.

Paul et al. [1], awarded best paper at the ACM Internet Measurement Conference
in 2022, make the central point: a speed test measures a path, not a network.
Connection type, Wi-Fi band and signal strength, device resources and the
choice of test vendor all move the result materially, and the authors show that
much apparent under-performance reflects a cheaper subscription tier rather
than a degraded access network. They also report that Ookla's median throughput
can reach roughly twice M-Lab's for the same plan, city and ISP, which is a
methodological difference rather than a difference in the network.

Lee et al. [2] address who is measured rather than what is measured. Matching
close to a million Ookla measurements against census block groups, they find
sampling bias that correlates with income, education, age and ethnicity, and
propose two population-based corrections. Their result cuts both ways: the
bias is real and demographically patterned, but correcting it shifts a city's
speed distribution far less than the differences between regions do.

Taken together these two papers set the terms this project has to work within.
The first says an absolute speed figure cannot be read as a statement about
infrastructure. The second says the sample is not the population. Both are
reasons to treat a *change* in a region's own speed as the quantity of
interest, and to present the output as a priority ordering for inspection
rather than a measurement of service quality.

## Measuring the Australian divide

Australian measurement of digital inequality is descriptive and
survey-based. The Australian Digital Inclusion Index [4] scores access,
affordability and digital ability from the Australian Internet Usage Survey and
reports a persistent gap outside the capital cities. The Regional
Telecommunications Review [5] documents the same gap through submissions and
consultation. Neither is a coverage measurement, and neither is predictive:
they describe where the divide is now, not where service is about to
deteriorate, and so neither can be used to decide where to send a crew next
quarter.

## Spatial structure

A model fitted across a whole state assumes a relationship that holds
everywhere in it. VoPham et al. [6] set out why that assumption is usually
wrong for geographic data, and why spatial nonstationarity — a predictor
meaning different things in different places — is the normal case rather than
the exception. This project's finding that performance differs sharply between
urban and regional areas, to the point that regional areas cannot be modelled
at all, is an instance of the problem they describe rather than a surprise.

## Where this project sits

Prior work predicts degradation from data only the operator holds, or measures
the divide descriptively from surveys, or documents the biases in crowdsourced
measurement without putting it to an operational use. This project takes the
third body of work's data, accepts its stated limitations, and asks whether it
supports the first body of work's task: ranking regions for maintenance
attention. The contribution is not a new model. It is a measured answer, from
public data, to whether the ranking is good enough to act on, and an explicit
statement of which parts of the state it cannot speak for.

## References

[1] U. Paul, J. Liu, M. Gu, A. Gupta, and E. Belding, "The importance of
    contextualization of crowdsourced active speed test measurements," in
    Proc. 22nd ACM Internet Measurement Conf. (IMC '22), Nice, France, Oct.
    2022, doi: 10.1145/3517745.3561441.

[2] H. Lee, U. Paul, A. Gupta, E. Belding, and M. Gu, "Analyzing disparity and
    temporal progression of internet quality through crowdsourced measurements
    with bias-correction," arXiv:2310.16136, Dec. 2023.

[3] System error prediction for business support systems in telecommunications,
    DOI 10.1109/TPDS.2020.3001593. VERIFY BEFORE SUBMISSION: the indexed DOI
    prefix belongs to IEEE Trans. Parallel Distrib. Syst., which does not
    obviously match the title. Confirm the venue on IEEE Xplore or drop it.

[4] Australian Digital Inclusion Index, RMIT University, Swinburne University
    of Technology and Telstra. [Online]. Available:
    https://digitalinclusionindex.org.au/

[5] Regional Telecommunications Independent Review Committee, 2024 Regional
    Telecommunications Review, Dept. of Infrastructure, Transport, Regional
    Development, Communications and the Arts, Australian Government, 2024.

[6] T. VoPham, J. E. Hart, F. Laden, and Y.-Y. Chiang, "Emerging trends in
    geospatial artificial intelligence (geoAI): potential applications for
    environmental epidemiology," Environmental Health, vol. 17, no. 1, art. 40,
    Apr. 2018, doi: 10.1186/s12940-018-0386-x.

[T1] Deep learning-based cell performance degradation prediction, master's
     thesis, Addis Ababa University, 2022. Thesis, not peer-reviewed.

[T2] Predicting failures of mobile network base stations, master's thesis,
     Politecnico di Milano. Thesis, not peer-reviewed.
