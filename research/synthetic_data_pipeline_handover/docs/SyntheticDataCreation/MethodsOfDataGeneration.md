1. Methods for Synthesizing Data | Practical Synthetic Data Generation

Chapter 5. Methods for Synthesizing Data

After describing some basic methods for distribution fitting in the last chapter, we will now use these concepts to generate synthetic data. We will start off with some basic approaches and build up to some more complex ones as the chapter progresses. We will refer to more advanced techniques later on that are beyond the scope of an introductory text, but what we cover should give you a good introduction.

Generating Synthetic Data from Theory

Let’s consider the situation where the analyst does not have any real data to start off with, but has some understanding of the phenomenon that they want to model and generate data for. For example, let’s say that we want to generate data reflecting the relationship between height and weight. It is generally known that height and weight are positively associated.

According to the Centers for Disease Control, the average height for men in the US is approximately 175 cm,1 and for the sake of our example we will assume a standard deviation of 5 cm. The average weight is 89.7 kg, and we will assume a standard deviation of 10 kg. For the sake of our example, we will model these as normal (Gaussian or bell-shaped) distributions and assume that the correlation between them is 0.5. According to Cohen’s guidelines for the interpretation of effect sizes, a correlation of magnitude equal to 0.5 is considered to be large, 0.3 is considered to be medium, and 0.1 is considered to be small. Any correlation above 0.5 would be a strong correlation in practice.2 Therefore, at 0.5 we are assuming a large correlation between height and weight. Based on these specifications, we can create a dataset of 5,000 observations that models this phenomenon.

We will present three ways to do this: (a) sampling from multivariate (normal) distributions, (b) inducing a correlation during the sampling process, and (c) using copulas. Each will be illustrated below.

Sampling from a Multivariate Normal Distribution

In the first method, we generate data from these two distributions by sampling from the density function, and during the generation process we can ensure that the generated values of height and weight are correlated at 0.5. In this example we want to generate 5,000 synthetic observations. Because the two variables are normally distributed, we can sample from a multivariate normal distribution. When we do that, we end up with a two-variable dataset with 5,000 observations with a correlation of 0.5, which is shown in Figure 5-1.

psdg 0501
Figure 5-1. A simulated dataset of 5,000 observations consisting of height and weight generated from a multivariate normal distribution

That was easy. And the basic process can be extended to as many variables as we want (i.e., we are not limited to two variables).

Inducing Correlations with Specified Marginal Distributions

Now let’s say that we want to generate data showing the relationship between a patient’s weight and their length of stay (LOS) at the hospital. The length-of-stay variable has an exponential distribution, as illustrated in Figure 5-2. We will assume that the correlation is weak between these two variables—say, 0.1.

psdg 0502
Figure 5-2. An exponential distribution representing the length of stay

Sampling from a multivariate normal distribution works well when we know that the distributions of the variables are normal. But what if they are not, as in the current example? We cannot generate this synthetic data from a multivariate normal because the length-of-stay variable is not a normal distribution.

In that case, we can sample from the normal and exponential distributions but at the same time induce the desired correlation during the sampling process.3 We then have the synthetic data distributions in Figure 5-3 with an actual correlation between them that was computed at 0.094, which is quite close to the desired correlation of 0.1.

This basic process can be further expanded to multiple variables. We can specify a correlation matrix of bivariate relationships among multiple variables and use the same process to induce the desired correlations as we are sampling.

psdg 0503
Figure 5-3. The generated synthetic data for weight and length of stay by inducing a correlation when sampling

This process can work well if we are able to specify the data distributions in terms of one of the classical distributions (e.g., normal, exponential, Beta, and so on). In Chapter 3 we discussed ways of finding the best fit of real data to the classical distributions.

Copulas with Known Marginal Distributions

Another approach for generating synthetic data is to use copulas to model marginal distributions that are different and still maintain the correlations among them. A key characteristic of copulas is that they separate the definition of the marginal distributions from the correlation structure, and they still allow the sampling from these distributions to create new data while maintaining the correlation structure.

In our last example we had two marginal distributions, a normal distribution and an exponential distribution. For our purposes, we will use a Gaussian copula. With a Gaussian copula we would generate observations from a standard multivariate normal distribution with a correlation of 0.1, and then map the generated values to our normal and exponential distributions through the cumulative density functions (CDF). This is called a probability integral transform. We compute the CDFs from standard multivariate normal distribution, and then compute the quantiles back to our exponential and normal distributions for LOS and weight. By using copulas we sampled 5,000 observations for the two distributions, and these are shown in Figure 5-4 with an actual 0.094 correlation between them, which is very close to the desired correlation.

psdg 0504
Figure 5-4. The generated synthetic data for weight and length of stay using a Gaussian copula

Again, the concept behind copulas can be extended to multiple variables, and when their marginal distributions are specified, the generated datasets will generally maintain the marginal distributions and bivariate correlations, even when the distributions are quite different from each other.

We are not limited to 5,000 observations. When generating the datasets, we can do so for much larger datasets, or very small datasets. The generated sample size will be a function of the analyst’s needs.

In the next section we will look at the case when we have real data and we want to synthesize data from that. In such a case, we do not have theoretical distributions to work from. This can happen when the phenomenon is complex or not well understood.

Generating Realistic Synthetic Data

When there is real data available, then the process described previously can be applied. The main difference is that we need to generate synthetic data based on a model of real datasets and not theoretical relationships. We will use an example of a hospital discharge dataset to illustrate this process. This example dataset is detailed in “A Description of the Hospital Discharge Dataset.”

We will need to fit the marginal distributions in our data to some kind of classical distribution. We discussed distribution fitting in more detail in Chapter 3. Therefore, we are still generating data from classical distributions, except that these distributions are derived from best fits with real data.

Fitting Real Data to Known Distributions

For our three hospital variables, we will first fit them to classic distributions. We determined that AGE follows a Beta distribution (multiplied by a constant, which in this case was approximately 100) and that both DSLS and LOS follow an exponential distribution. Then to generate the synthetic data we can sample from the fitted distributions, as described previously, and induce the same correlations as the original data.4 The sampling process can generate synthetic datasets of any size (the synthetic data can be much larger or smaller than the original data).

This process gives us the correlations in Figure 5-6. As you can see, the synthetic data correlations are quite close to the real correlations.

psdg 0506
Figure 5-6. A correlation matrix giving a comparison between the original correlations and the synthetic correlations for pairs of variables in the hospital discharge data. The values in parentheses are the original correlations, and the values above them are the induced correlations in the synthesized data.

The problem here is that the fitted distributions (Beta and exponential) are not good fits to the real data. We can see that in Table 5-1. These were the best distributions from the most common known ones that we could fit with. In that table, the Hellinger distance is an interpretable measure of how similar the distributions are.

Table 5-1. The Hellinger distances between the samples from the fitted distributions and the real variables from the hospital discharge dataset
Variable	Hellinger distance
AGE

0.972

DSLS

0.910

LOS

0.917

Let’s try doing the same thing with Gaussian copulas, where we generate synthetic data that matches the fitted distributions from the real data. The correlations among the variables are shown in Figure 5-7. As can be seen, the generated data does maintain the correlations quite well.

psdg 0507
Figure 5-7. A comparison between the original correlations and the synthetic correlations for pairs of variables in the hospital discharge data. The values in parentheses are the original correlations, and the values above them are the correlations using data generated with a Gaussian copula.

The Hellinger distances for the marginal distributions generated using the Gaussian copula are the same as shown in Table 5-1. The conclusion is the same as before: the fits are not that convincing.

Therefore, when we try to fit classic distributions to real data, the fits may be the best available, but that does not mean that they will be very good. Of course, the veracity of that last statement will be data dependent, but we work with complex health and consumer data, and we often see poor fits. We need to find a repeatable and scalable solution that will work for all kinds of real data.

Using Machine Learning to Fit the Distributions

As we saw in the previous chapter, we can use machine learning models to fit the distributions. This allows us to build a model that can generate synthetic data that more faithfully reflects the real distributions in the data. With these ML fitted distributions, we can then apply these distributions with the methods of inducing a correlation and with copulas.

The similarity between the fitted distributions and the real distributions is quite high, as illustrated in Table 5-2. We can use these fitted models to generate marginal distributions of any size.

Table 5-2. The Hellinger distances for the synthetic marginal distributions using a machine learning method for fitting a model to the real marginal distributions
Variable	Hellinger distance
AGE

0.0001

DSLS

0.001

LOS

0.04

We will now also use the distinguishability metric that we discussed in the utility chapter. This tells us how similar the synthetic dataset is to the real dataset. The summary in Table 5-3 shows the distinguishability metric for the three approaches. With the methods of inducing correlations during sampling and Gaussian copulas, we used the ML fitted distributions instead of the known distributions. As can be seen, the distinguishability is low across the board, and all of the methods produce very comparable results.

Table 5-3. The distinguishability between the real and synthetic data when distributions fitted to the real data using machine learning models are used
Method	Distinguishability
Inducing correlations

0.005

Gaussian copulas

0.02

Decision trees

0.003

The key lesson here is that the machine learning models are far superior to modeling distributions of real datasets. They will generally outperform trying to fit real data to classic distributions.

Hybrid Synthetic Data

Now let’s consider the situation where we want to create hybrid data. This is where one part of the synthetic data is based on real data, and the second part is based on a theoretical understanding of the phenomenon, but we do not actually have data. In essence, this is adding signal to the data.

Taking our example of the hospital data, let’s add a new variable indicating the number of cigarettes smoked and then synthesize the dataset using a Gaussian copula. This would have an exponential distribution where 86% of individuals do not smoke (ensuring consistency with the general population). The assumed correlations that we have added to the original data are shown in Figure 5-8. Here we assumed that there is a weak positive correlation with age, and a moderate negative correlation with DSLS, and a moderate positive correlation with LOS. The real data correlations are shown in parentheses in the diagram. As can be seen, the overall correlation structure has been maintained quite well in the data that was synthesized.

psdg 0508
Figure 5-8. The correlation matrix showing real and synthetic data that was generated using a copula. The values in parentheses are the original correlations, and the values below them are the induced correlations in the synthesized data.

We can now use the methods that were examined earlier to synthesize a dataset that is partially based on real data and has additional signals added to it, while maintaining the original correlations. Again, we can see the Hellinger distances comparing the synthetic distributions to the real data for the three real variables using both methods in Table 5-4.

Table 5-4. The Hellinger distances for the synthetic marginal distributions using a Gaussian copula to generate the hybrid data
Variable	Hellinger distance
AGE

0.0036

DSLS

0.004

LOS

0.007

Smoking

0.006

This synthetic dataset merged real information with hypothetical information to generate a hybrid. The basic principles can be easily extended to more variables and used with other techniques.

The set of methods we have described here provides a toolbox for the generation of artificial, realistic, and hybrid data. Furthermore, the methods can be extended to an arbitrary number of variables to create quite complex datasets.

Machine Learning Methods

We will examine a representative machine learning method for the generation of synthetic data. We will use a decision tree, although any kind of regression and classification method can be used. The principle for each is the same in that we sequentially synthesize variables using classification and regression models. For the decision tree we use CART (see “Sequential Machine Learning Synthesis”).

The marginal distribution results on our hospital discharge data are shown in Table 5-5. Here we can see quite a good match between the synthesized distributions and the original ones.

Table 5-5. The Hellinger distances for the synthetic marginal distributions using a machine learning method to generate all of the synthetic datasets
Variable	Hellinger distance
AGE

0.0033

DSLS

0.005

LOS

0.0042

We can similarly see concordant correlations between the synthetic and the original data. Therefore, the tree was able to retain a good amount of the data utility. The distinguishability metric was 0.003, which is also quite low, indicating that the synthetic data retained much of the structure of the original data. See the matrix in Figure 5-9, which illustrates the correlation between variables in the original and synthetic datasets.

psdg 0509
Figure 5-9. The correlation matrix for the hospital data generated using a decision tree. The values in parentheses are the original correlations, and the values above them are the induced correlations in the synthesized data.

Deep Learning Methods

There are two general types of artificial neural network architectures that have been used to generate synthetic data. Both can work well, and in some cases they have been combined.

The first is the variational autoencoder (VAE). It is an unsupervised method to learn a meaningful representation of a multidimensional dataset. It first compresses the dataset into a more compact representation with fewer dimensions, which is often a multivariate Gaussian distribution. This acts as a bottleneck. The encoder performs that initial transformation. Then the decoder takes that compressed representation and reconstructs the original input data, as illustrated in Figure 5-10. The VAE is trained by optimizing the similarity between the decoded data and the input data. In this context, a VAE functions similarly to principal component analysis, except that it is able to capture nonlinear relationships in the data.

psdg 0510
Figure 5-10. A high-level view of how a VAE works

Another architecture is the generative adversarial network (GAN). With a GAN there are two components, a generator and a discriminator. The generator network takes as input random data, often sampled from a normal or uniform distribution, and synthetic data is generated. The discriminator compares the synthetic data with the real data—creating a propensity score similar to what we saw before. The output of that discrimination is then fed back to train the generator. A good synthetic model is created when the discriminator is unable to distinguish between the real and synthetic datasets. A GAN architecture is shown in Figure 5-11.

psdg 0511
Figure 5-11. A high-level view of how a GAN works

Both of these approaches have demonstrated quite high synthesis utility on complex datasets and are a very active area of research.

Synthesizing Sequences

Many datasets consist of sequences of events that need to be modeled. Here we will assume that the dataset has a series of discrete events. For example, the dataset may consist of healthcare encounters, such as visiting a doctor, getting a lab test done, going to get a prescription, and so on. An example of such a dataset is illustrated in the data model in Figure 5-12.

psdg 0512
Figure 5-12. An example of a complex health dataset with multiple sequences

Here we have a relational data model with some patient demographics for each patient. Then there are possibly multiple events reflecting the drugs that have been prescribed to that patient over time. There can also be multiple events per patient, one for each visit to the clinic. A patient may be admitted more than once to the hospital over the period of the data collection. There may also be multiple lab tests and insurance claims per patient. Thus in the dataset there will be multiple events occurring per individual over time.

Some of these events, such as death, may end the sequence; or, if the event is a study, there can be another event signifying the end of the study. In many cases, these datasets will also be ordered.

To synthesize this dataset, we need to first compute the transition matrix among all of the events. This can be estimated empirically by looking at the proportion of times that a particular event follows another one. For instance, let’s say that we have four events A, B, C, and D. And let’s say that C is a terminal event, in that nothing comes after C in terms of outgoing transitions. If 40% of the time an event B follows an event A, then we can say that the transition from A to B has a probability of 0.4.

Creating such a transition matrix assumes that an event is dependent on only one previous event. This can be quite limiting, and the synthesis will not be able to capture longer-term trends. Therefore, we can assume that an event depends on the previous two events (or more—that is a design decision; for our purposes though we will assume that we want to capture two previous events).

An example of a transition matrix is shown in Figure 5-13. Here we have the two previous events, in a particular order because in a healthcare context the order will matter, along with the transition probabilities. The rows indicate the previous states, and the columns indicate the next state. Each row needs to add up to 1 because the sum of the total transitions from a pair of consecutive states must be 1. Also, there are no previous states with a C event in them because that is a terminal event.

psdg 0513
Figure 5-13. An example of a transition matrix with four events, with C being a terminal event and an order of two

For every individual that we want to synthesize for, we need to determine the start state. The start state can be synthesized from other data. But this is still not sufficient. We need to construct another transition matrix from the start state to the second state. This is illustrated in Figure 5-14. This acts as a “starter” transition matrix.

psdg 0514
Figure 5-14. An example of a transition matrix for starting the generation sequence

For each patient, we can begin from their starting state and then select the next state randomly according to the transition probabilities. For example, if the starter state is A, then there is a 40% chance that the next state is B. Let’s say that B was selected. Then we have a sequence of AB. We then start from the AB row (Figure 5-13) in the second transition matrix and go on a random walk through that matrix until we hit a terminal node. For example, after AB we may randomly select another A event. Now the previous two events are BA, which may lead to a C event, and that would be the end of the sequence for that individual. This is repeated for however many sequences we want to generate.

Once a sequence is generated, we can compute the Hellinger distance between each row of the synthetic transition matrix and the real data matrix to evaluate how similar that sequence is to the original data. A median across all rows would provide an overall measure of similarity of sequences.

This approach works well but has some limitations, which we will summarize in the following paragraphs.

The example we looked at considered only two historical events. For complex datasets, the history that needs to be taken into account would be larger, otherwise the generated utility may be limited. We can create transition matrices with more history, of course. This can be done if there is sufficient data to estimate or compute the transition probabilities; otherwise, these can be somewhat unstable.

Another common challenge is that some events do not have an order that is discernible from the data. For example, during a hospital visit, there may be lab tests and diagnostic imaging events. The data will likely capture these events not by the minute but by the day. Therefore, all of these events effectively occurred at the same time.

The interval between events would need to be considered as well. For example, some events will happen a week apart, and some will happen months apart. The interval may not be fixed (of course, that will depend on the dataset). In a health dataset, for example, these intervals can vary quite a bit between events for the same individual. And the interval information is very important because many analyses will look at time to event (for example, the survival time of cancer patients).

Finally, the events may have additional attributes associated with them. For example, a lab test event will have the results of the lab test associated with that event. We did not consider these attributes in this description.

Therefore, modeling sequence, or longitudinal, data in the manner described previously is a good starting point, but it has limitations hat would require more advanced techniques to be applied. For this type of data, recurrent neural networks would be a good way to model the sequences and take into account more of the history.

Summary

In this chapter, we outlined a few methods that are relatively straightforward to implement for data synthesis and that in practice will give good results in terms of data utility. We also provided some direction for handling sequential data.

As a general recommendation, data synthesis with machine learning methods will provide better data utility than inducing correlated data and using copulas, although the latter are both useful techniques to have available for simpler datasets.

When datasets get more complex, machine learning and deep learning methods will perform better. Furthermore, there are no real practical techniques to handle high data complexity except machine learning and deep learning models. There has not, however, been a comprehensive comparison of these methods. Different analysts choose a method they prefer and continuously optimize it.

Important criteria for choosing a synthesis method are that it works with the types of data that you need to synthesize and that it does not require extensive tuning to work.

There are small datasets, for example, with which deep learning techniques may struggle to perform well. In such cases, statistical machine learning techniques could be a good option. Also, statistical machine learning methods can easily work with datasets that are heterogeneous with a mix of continuous, categorical, and binary variables.

To enable the wider adoption of data synthesis, we do not want to be continuously tweaking the parameters of the synthesis models to get them to work. Ideally, a synthesis approach would produce pretty good results all of the time without much labor. That way synthesis can be used by nonexperts in the domain or in the synthesis techniques. The greater the burden, the fewer people will be able to use the methodology.

In the next chapter, we will examine the other side of the ledger: privacy. While we can create high-utility data, it is also important to ensure that the privacy risks are managed. Privacy assurance is an important capability when synthesizing data. In today’s regulatory environment, the liability to an organization can be significant if it uses synthetic data as if it is not personal data and then finds out later that the privacy risks were still high.

1 Cheryl D. Fryar et al., “Mean Body Weight, Height, Waist Circumference, and Body Mass Index Among Adults: United States, 1999–2000 Through 2015–2016,” National Center for Health Statistics, December 2018. [https://oreil.ly/bgf9i](https://oreil.ly/bgf9i).

2 Jacob Cohen, Statistical Power Analysis for the Behavioral Sciences, 2nd edition (Mahwah: Lawrence Erlbaum Associates, 1988).

3 Ronald L. Iman and W. J. Conover, “A Distribution-Free Approach to Inducing Rank Correlation Among Input Variables,” Communications in Statistics - Simulation and Computation 11, no. 3 (1982): 311–334.

4 Ronald L. Iman and W. J. Conover, “A Distribution-Free Approach to Inducing Rank Correlation Among Input Variables,” Communications in Statistics - Simulation and Computation 11, no. 3 (1982): 311–334.

5 Leo Breiman et al., Classification and Regression Trees (Milton Park: Taylor & Francis, 1984).
