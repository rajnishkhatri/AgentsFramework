3. Getting Started: Distribution Fitting | Practical Synthetic Data Generation
Chapter 3. Getting Started: Distribution Fitting

A straightforward way to think about the process of data synthesis is that we are trying to model both the distributions of the real data and the structure of the real data. Based on that model we can then generate synthetic data that retains the characteristics of the original data. In this chapter we cover the first step in that process—modeling distributions. Once you know how to do that, we’ll move on to modeling the structure of the data in Chapter 5.

The starting point of modeling distributions is understanding how to fit individual variables to known distributions (or “classical” distributions, such as the normal and exponential). Once we are able to do that, we can generate data from these distributions that have the same characteristics as the original data.1

The next step will be to enable the modeling of nonclassical distributions. Some real-world data or real-world phenomena do not follow a classical distribution. We still want to be able to synthesize data that does not follow classical distributions. Therefore, we outline how machine learning models can be used to fit unconventional data distributions.

Framing Data

Any data analysis task begins with a pile of data that needs to be transformed into a data frame. A data frame is a table of data in which each row, also known as a record, is a complete, self-contained example of the data being represented. Each column, also known as a variable or field, is a detail about the record. Every field in a column must be of the same data type.

Framing the data can be hard work. Columns must be regimented into the expected data type; errors and exceptions need to be weeded out; relational data must be unfolded into the frame by joins; missing data needs to be estimated, extrapolated, neutralized, or omitted. This requires knowledge about the data that is not in the data, notably knowledge about what to expect. Like my hairdresser, the person who does the data preparation is not going to be replaced by artificial intelligence anytime soon.

Once data has been framed, a substantial arsenal of analytical weaponry developed in the last three hundred years can be deployed to dissect it, from the probabilities of Thomas Bayes to the machine learning guiding the electrons-with-consequences in our increasingly virtual world today. We can use these techniques to model a data frame’s distributions and probabilities, forecast future values, measure how much information it contains, estimate the error around any data model we create, and create control strategies for optimizing real-time data in real time. So many exciting things.

But the topic of this book is data synthesis, which brings in a new angle: anonymity. Not only do we need to model the distribution of real data and then create synthetic data that fits it well, but we also have to ensure that the original data cannot be determined from the synthetic data. There will be more on the privacy question later in the book.

Once we have a data frame, we need to understand and model the distribution of the fields within it.

How Data Is Distributed

Individual data variables can have many types and distributions. The following are among the most common:

Unbounded real numbers, potentially ranging from –infinity to +infinity—for example, the Gaussian or normal distribution, which tends to apply when random numbers are added together, as in Figure 3-1.

psdg 0301
Figure 3-1. Example of a normal distribution for the difference between a husband’s and wife’s ages

Bounded real numbers with definite upper and lower bounds—for example, Bayesian probabilities ranging from 0 to 1, or, equivalently, 0% to 100%. These are particularly useful for expressing the likelihood of an estimate or confidence level, as in Figure 3-2.

psdg 0302
Figure 3-2. Example of a Bayesian distribution illustrating the likelihood that a defendant is innocent

Nonnegative integers—for example, Poisson distributed counts of events, ranging from 0 to n, in Figure 3-3.

psdg 0303
Figure 3-3. Example of a Poisson distribution illustrating the number of rainy days per month in San Francisco

Logarithmic distributions, which may be integers or real numbers and tend to reflect physical systems with multiplicative effects—for example, Benford’s distribution of first digits in accounting numbers, as in Figure 3-4.

psdg 0304
Figure 3-4. Example of a logarithmic distribution illustrating the distribution of accounting numbers

Binomial integers, which model the number of successes from a series of independent experiments—for example, the probability of the number of heads from 10 coin tosses, as in Figure 3-5.

psdg 0305
Figure 3-5. Example of a binomial distribution showing the probability of a specific number of heads in 10 coin tosses

Nonclassical distributions based on physical realities—for example, the hospital discharge data in Figure 3-6. This shows the distribution of ages of individuals who were discharged from hospitals in a specific US state.

psdg 0306
Figure 3-6. The distribution of ages of individuals discharged from a hospital

Factor data, or category data, has a definite number of categories, as in Figure 3-7.

psdg 0307
Figure 3-7. The probability of being in a particular astrological sign—an example of a factor distribution

Factor data is a little different from other types of data because a factor’s relationship with other factors is not linear:

It may have sequence: birth, marriage, death events, with the second being optional and not necessarily unique

It may have quasi-sequence: Sunday, Monday, Tuesday… (peppered with national holidays!)

It may have no sequence: red, green, blue…

To work with the established analytical techniques, factor data needs to be turned into numbers. The usual approach is to split the factor into multiple variables, one for each factor, containing 1 if it is that factor and 0 if it isn’t (this is also called one-hot encoding). This approach excludes some analysis techniques such as multivariate regression, due to matrix inversion failure. However, when used with more advanced neural network modeling techniques, it has the advantage that the results are in the range 0 to 1 and represent probability of a particular factor being right.

The challenge with this approach is that when there are many categories, this results in a large number of new variables being added to the dataset. A more efficient alternative is binary encoding, in which each factor is encoded into its binary equivalent. For example, if we have five possible values, then the third value is encoded “011.”

Time series data contains records of sequential measurements in which the probability distribution for the present record will depend on earlier measurements. In data science courses, the time to the next eruption of the Old Faithful geyser in Yellowstone National Park is a common teaching example, and is illustrated in Figure 3-8.

psdg 0308
Figure 3-8. Modeling Old Faithful eruptions

Similarly, in financial markets, price changes relative to previous values are quite important. The Dow Jones Industrial Average (DJIA) over the last five years can be seen in Figure 3-9.2

psdg 0309
Figure 3-9. Financial market time series

But do we care what the actual stock price is? People are more interested in knowing how much their investment is now relative to when they bought in. That, again, raises questions: What time horizon is relevant? Is the time horizon eroding my data quality? The charts shown in Figures 3-10 and 3-11 show data rebased (or recalculated) from Figure 3-9 as a percentage change over time, and they indicate the data erosion penalty. (And they give a lesson in long-term rather than short-term investing!)

psdg 0310
Figure 3-10. One-month returns based on Dow Jones data

psdg 0311
Figure 3-11. One-year returns based on Dow Jones data

Time series data gets worse. Longitudinal data (for example, maintenance records or doctor’s visits) is composed of sparse records that are taken at sporadic intervals but that happen in a clear sequence and can be modeled by Markov chains, which is beyond the scope of this chapter.

Finally, unstructured data, such as Twitter feeds or doctor’s notes, can really be applied only if they can be structured in some manner—for example, using keywords to create sentiment indicators, which is again beyond the scope of this chapter.

Fitting Distributions to Real Data

Fitting a distribution to individual variables (univariate distributions) is, on the surface, fairly straightforward. An error function, such as squared error, can be used to measure how close a distribution is to the real data. Frequency distribution functions are parameterized equations. For example, Gaussian distributions have mean and standard deviation parameters; machine learning models have neural network weights. Fitting is searching for the parameters that optimize the error function, and plenty of optimization algorithms exist to help us do that.

Modeling univariate distributions, however, is often not enough. Let’s revisit Old Faithful and plot the probability density for each variable along its axis, as in Figure 3-12.

psdg 0312
Figure 3-12. Old Faithful data with the probability density along each axis

If we blindly generate synthetic data according to those distributions, the synthesized data will have unintended ellipses of high density, as shown in Figure 3-13.

psdg 0313
Figure 3-13. Old Faithful data illustrating high-density ellipses

What we really need is a “multivariate” probability, which is a distribution that takes into consideration both variables at once, as in Figure 3-14.

psdg 0314
Figure 3-14. Old Faithful data illustrating synthesis from a multivariate distribution

Note that by considering both variables together, we have not only removed the unintended ellipses of high density but also allowed the desired ellipses to rotate.

Generating Synthetic Data from a Distribution

If the fitted distribution is a known or classical one, and the fitting process has determined the distribution parameters, then synthetic data can be generated using Monte Carlo methods. That is, data is just sampled from these distributions.

The brute-force approach to generating synthetic data from nonclassical distributions is straightforward: generate randomized datapoints evenly across the data range, or as probability suggests, and adopt or reject it according to whether it improves the fit to the distribution.

More sophisticated methods exist, such as using histogram equalization to generate distributed synthetic data from uniform random data, but with sufficient computing capacity, it can be easiest to keep it simple.

Measuring How Well Synthetic Data Fits a Distribution

Several measures exist to grade how well a probability distribution fits to a single variable within a dataset, including the Chi-squared measure and the Kolmogorov-Smirnov (KS) test.

KS is particularly robust because it looks at the difference between the cumulative probability and the cumulative data count, which makes it fairly indifferent to the actual distribution of the data. Let’s plot the cumulative distribution of the probability (assuming it follows a quadratic distribution) and sample data in Figure 3-6 in Figure 3-15.

The KS measure is essentially the area between the two curves. The smaller the area, the better the fit of the distribution to the data.

Extending the KS approach to multiple dimensions is tricky: it is not easy to define cumulative across many variables of different types, with a sparse dataset occupying tiny pockets within the total volume of space. One approach is to use the sparse dataset as a guide to what is important, limiting the measurement to areas where data exists.

psdg 0315
Figure 3-15. KS test of hospital discharge data

The Overfitting Dilemma

Let’s take a look at the hospital discharge rate again. The red line in Figure 3-16 is a quadratic fit based on three variables and is a generalization of the 51-datapoint distribution.

psdg 0316
Figure 3-16. The hospital discharge data with a best fit standard distribution

We can improve the fit by using models with more variables. For example, a spline might produce something like Figure 3-17.

psdg 0317
Figure 3-17. Overfitting to a distribution of hospital discharge ages

While this passes through every datapoint, can it be justified? For example, given that we don’t have any evidence for there being a sudden peak at 50, should we incorporate it into the model? This is known as the problem of overfitting, where we start to fit to artifacts in a particular dataset, rather than to the actual distribution that the sample represents. We’re probably looking for something more like Figure 3-18.

psdg 0318
Figure 3-18. Better fit to a hospital discharge age distribution

This issue is widespread and causes many problems. Models that appear to fit well don’t perform well when applied to new data because the analyst tried too hard to fit to the old data.

The problem is acute when the intent is to anonymize data by synthesis: overfitting gives away the original data, defeating the object of the exercise.

Solving this problem requires two things. The first is an approach that allows a distribution to start from a neutral point and journey slowly to a closer and closer fit to the data, trading off between simplicity of distribution and goodness of fit at each step. The second is a measure to know when the best trade-off point has been reached.

Most distribution-fitting approaches can find some kind of journey from a neutral start to an overfitted state. A B-tree, for example, can add more and more branches; neural networks can use weight pruning or steepest descent (my favorite for its purity); radial basis functions can add more bases.

A measure to know when the best trade-off point has been reached requires a sub-sample approach. Let’s go back to how we expressed it a few paragraphs ago: models that appear to fit well don’t perform well when applied to new data because the analyst tried too hard to fit to the old data. So somehow we need to measure how representative the data is of the distribution from which it comes.

How can we do that without more data to compare it to? We can’t, so we do the next best thing: we hold back some of the data (i.e., create a holdout sample, which can be, say, 25% or 33% of the training dataset) and see how well it fits to the distribution created with the rest of the data. What we see is something like Figure 3-19.

psdg 0319
Figure 3-19. Ensuring that the model does not overfit the data

Notice how the goodness of fit to the holdout sample reaches a peak and then, as overfitting starts to happen, drops off, even though the in-sample fit continues to get better. In this example, the optimal fit occurs at 50 steps. The fitting process can then be repeated without the holdout sample, stopping at the 50th step to avoid overfitting and thus finding the optimum trade-off between goodness of fit and the risk of identification.

With small datasets, the process is repeated with multiple holdout samples in order to determine the optimum trade-off point.

A Little Light Weeding

This process allows univariate synthetic data to be generated that retains as much of the underlying structure as possible without capturing so much information that the original data can be identified. However, a synthetic datapoint could be generated that is coincidentally close to one of the original datapoints. Therefore, as a final step, it is worth checking whether this is the case and rejecting any datapoints that are too close.

Summary

In this chapter we first looked at classical distributions and how we can fit real data to them. Many real datasets do not follow classical distributions, and therefore there will be a mismatch between the fitted distributions and the real data. One can use machine learning models to learn the distribution of the data. This allows the modeling of nonclassical distributions that can be multimodal, which can be heavily skewed or have other unusual characteristics. However, when we do that we need to be aware of the risk of overfitting and ensure that we are learning the distribution in a manner that is generalizable to other data.

In the next chapter we will start exploring the second component of data synthesis: modeling the structure of the data. The first step in that process is to look at ways to evaluate data utility. To understand what is a good data structure, we need to be able to define and measure the concept of a good data structure.

1 Chong K. Liew, Uinam J. Choi, and Chung J. Liew, “A Data Distortion by Probability Distribution,” ACM Transactions on Database Systems 10, no. 3 (September 1985): 395–411.

2 At the time of the final editing of this book, the market conditions changed dramatically. Therefore, this is only an example reflective of the good old days.
