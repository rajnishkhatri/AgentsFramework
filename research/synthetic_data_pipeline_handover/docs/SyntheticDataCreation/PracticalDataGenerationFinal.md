7. Practical Data Synthesis | Practical Synthetic Data Generation
Chapter 7. Practical Data Synthesis

Real data is messy. When data has been cleaned up and heavily curated, then data synthesis methods (and for that matter any data analysis methods) become much easier. But the actual requirement in practice is to synthesize data that has not been curated.

This chapter presents a number of pragmatic considerations for handling real-world data based on our experiences delivering synthetic datasets and synthetic data generation technology. While our list is not comprehensive, it covers some of the more common issues that will be encountered. We highlight the challenges as well as provide some suggestions for addressing them.

At this point, we do not make explicit assumptions about the scale of the data that will be synthesized. For example, some datasets, such as financial transactions or insurance claims, can have a few variables (tens or maybe even hundreds) but a very large number of records. Other datasets can have few individuals covered but a large number of variables (thousands or tens of thousands). These narrow and deep versus wide and shallow datasets present different challenges when processing them for data synthesis. In some cases, the challenges can be handled manually, and in other cases full automation is a necessity.

Managing Data Complexity

The first set of items that we want to cover pertains to how to manage data complexity. If you work with data then you are used to handling data challenges. In the context of synthesis there are some additional considerations.

For Every Pre-Processing Step There Is a Post-Processing Step

The data users expect their synthetic data to have the same structure as the real data. This means that the variable names have to be the same, the field types need to be the same, and the data model for the real data has to be maintained in the synthetic data. However, the data synthesis methods that we discussed need inputs in a certain format. The data may have to be scaled to be within a certain range (say, 0 to 1) and all of the data tables joined to create a single data frame. All such data pre-processing steps must be undone during the post-processing step.

We are making a distinction between data preparation and data pre-processing. Data preparation can be performed by the data provider. For example, if there are multiple datasets that are being pooled together, a certain amount of data harmonization has to be performed beforehand. Data preparation needs to be performed, typically, for any kind of data analysis work and not just for data synthesis. This would similarly be the case when different datasets are being linked to create an integrated dataset to work with. Such data integration happens during the preparation stage by the data providers.

Data shaping, on the other hand, is a synthesis pre-processing step. For example, data with attribute-value pairs are often difficult to work with in standard statistical analysis tools, and therefore this data will need to be reshaped into a more common tabular format. The synthesis pre-processing is part of the methodology and technology, and will be closely tied to the methods used for data synthesis.

Field Types

The pre-processing of datasets for synthesis will depend largely on the type of fields. For example, a continuous variable is pre-processed quite differently than a nominal variable. For large datasets with hundreds or thousands of variables it is not practical to do this classification manually. It is therefore important to be able to autoclassify field types to determine in an efficient manner the best way to pre-process and post-process each variable.

While this seems like a trivial thing to do, when there is no metadata, and domain knowledge is limited, it is not trivial at all.

The Need for Rules

It is quite common that datasets have deterministic relationships. Examples of these are calculated fields where the inputs are other fields, such as BMI (body mass index), which is calculated from height and weight. This relationship is deterministic. But the synthesis methods are mostly stochastic and will have some error in them when synthesized. It is better to detect these deterministic relationships in advance and remove the calculated fields before synthesis. Then after the covariates are synthesized, these derived values are calculated and inserted into the synthetic data.

Calculated fields show up in questionnaires and surveys—for example, where an index score is computed from the responses to the questions. Deterministically derived fields can be interpretations from laboratory results based on some rules. For example, if a lab result exceeds a threshold, then it is considered not normal.

In large datasets, manually documenting every calculated field can be time-consuming. In such cases, methods are needed to automatically detect such rules in the dataset and perform the necessary pre-processing and post-processing steps.

Not All Fields Have to Be Synthesized

There will almost always be at least one field that is a unique identifier. This could be a Social Security number, for example, that is used to identify every individual in the dataset. Or it can be a hospital identifier or a subject ID in a clinical trial dataset. For more complex datasets there will be more than one—for example, an identifier for every visit that the person makes to a hospital or a bank, and a unique transaction identifier for every drug that is dispensed from the pharmacy or item sold at the store.

The methods we have described thus far would not apply to unique identifiers. As a first step, it will be necessary to detect these unique identifiers in the original dataset. In many instances that is relatively straightforward to do because these fields will have the same number of values as there are records. But that is not always the case. Sometimes we see orphan records that do not have unique identifiers. A decision needs to be made about the orphan records. From a data synthesis perspective they can be synthesized, but if the unique identifiers link multiple sources of information, then the correlations with other information about these individuals will not be accounted for.

Sometimes there are compound unique identifiers. These are more challenging to detect, and a good understanding of the data model is needed to find them. A compound identifier is when more than one field makes up the unique identifier.

Once the unique identifiers are found, they are then pseudonymized in the synthetic data. There are multiple methods for pseudonymization. Cryptographic techniques can be used for that purpose (e.g., encryption or hashing), or the unique identifiers can be replaced by random values that are a one-to-one mapping to the original identifiers.

It is recommended that you prepend a special character (such as an “s_”) to the synthetic pseudonymized values. This will ensure that the data users do not mistake the synthetic data for real data. Knowing the provenance of the dataset is important. However, adding an “s_” at the beginning of the pseudonymized values may not work if the value is an integer and we want to maintain field types. Therefore, other mechanisms may need to be used.

Synthesizing Dates

The synthesis of dates needs special consideration. There are at least two types of dates. We will call them demographic dates (date of birth, date of death, date of marriage) where the exact date (or an approximation of it) is important. And there are event dates where the interval between them is the most important.

Demographic dates can be represented as an integer and synthesized using the traditional approach for integers. For example, demographic dates can be treated as the number of days since January 1, 1990.

For event dates, it is easiest to convert them to relative dates. This means that an anchor date that is specific to the individual (and that exists for all individuals in the data) is selected, and all dates are converted to days since that anchor. For example, in a clinical trial dataset it can be the date of randomization or date of screening. In an oncology dataset it can be the date of diagnosis. For a financial services dataset it can be the date the individual became a client or opened an account. Then the relative dates can be synthesized.

When there are multiple related dates and no obvious anchor to use, it is important to maintain the relationships among the dates. For example, the synthesized dataset should not have a date of discharge that occurs before a date of admission. In such a case, a length of stay can be calculated and the admission date is synthesized. Then the discharge date is computed after synthesis using the synthesized length of stay and admission date. Caution is needed to manage these temporal relationships.

Alternatively, we can add an independent random offset to each patient’s dates. That way the relative intervals are maintained, but no exact dates are retained.

In datasets with a large number of events, there are a few ways to deal with the temporal nature of the data. One approach is to “flatten” the data and have all of the events appear as columns. This works well when all the individuals in the dataset will have the same series of events. For example, this happens in clinical trials in which the visits are preplanned or in oncology datasets in which the treatment plans have a predetermined schedule. With such a flattened dataset, commonly used cross-sectional data synthesis techniques can be applied. In other cases where the data is more transactional, more sophisticated methods that account for the temporal dependencies would be needed for accurate data synthesis.

Synthesizing Geography

A typical example of a geographic variable is a zip code or a postal code. Since these are nominal variables in a dataset, they can be treated as other nominal variables and synthesized.

If location is captured by longitude and latitude, there is more complexity because the synthesized locations cannot be, for example, in the middle of the ocean or in a mine. Therefore, again, auxiliary information is needed to handle location.

In practice, more traditional data protection methods, such as generalization or perturbation of locations, are used here. Exact location fields cannot be treated in the same manner as other fields in the dataset.

Lookup Fields and Tables

Some datasets will have lookup fields. This is when the value in a field is a key to look up the true value in a different table. In general this is not a problem because the synthesis process can work equally well on the lookup values instead of the actual values. However, in such cases the lookup tables themselves should not be synthesized. The detection and carving out of these tables is an important step in pre-processing.

Missing Data and Other Data Characteristics

Real data will have missing values. These are generally not a problem for synthesis because the synthesis process will just replicate the missingness patterns in the original data. In some cases, the data synthesis analysts will try to impute the missing values before synthesis, and then synthesize from a complete dataset. This can also be performed as long as the imputation is performed reliably; the only caveat is that this adds significantly to the complexity of the synthesis project, and end-user data analysts will likely want to have control of the imputation process.

The general assumption is that other data quality issues have been dealt with prior to the synthesis process. If not, then these data quality issues will be reflected in the synthetic data—data synthesis does not clean dirty data. For example, if the coding scheme used in a variable is not applied consistently (e.g., it was entered manually and has errors, or different versions of the same coding dictionary were used over time with no version indicator), then that characteristic will be reflected in the synthetic data.

Under the general scheme that we have described in this book, text fields cannot be synthesized. While there is a whole body of work on the synthesis of text, we have not addressed that here. Therefore, we are assuming that text fields will be deleted from the synthesized datasets for the time being.

Datasets that consist of long sequences, such as genomic data, have a specialized set of techniques for their synthesis, similar to text. Long sequences also show up in movement trajectories (e.g., cars, people, and trucks). Trajectories have location and temporal complexities added to them—in that sense every event in the sequence has a number of attributes associated with it. The methods we have discussed in this book will not address these types of data, and synthesizing this kind of information represents areas of ongoing research.

Partial Synthesis

Some datasets are quite complex, and the synthesis process needs to maintain a large amount of information between the entities. When these entities are individual records rather than tables, the complexity can be significant. For such datasets the solution is to create a partially synthetic dataset. This is when some of the variables are synthesized, and some other variables are retained. This is similar to the approach that is used with traditional de-identification methods. However, with partial synthesis the number of synthesized variables can still be quite large.

When partial synthesis is used, it is recommended that the organization or analyst perform a privacy assurance check on every dataset that is generated. This provides additional assurance that the privacy risks have been managed.

Organizing Data Synthesis

The success of synthetic data generation projects depends on a set of technical and change management factors. Change management is used here to refer to the activities that are needed to support the analyst and analytics leadership in changing their practices to embed the use of synthetic data into their work. The practices we cover in the following sections can have an outsize influence on the outcome of implementing data synthesis.

While the amount of manual effort to synthesize data is relatively small, many data synthesis methods are computationally intensive. Therefore, we first discuss the importance of computing capacity. We next consider the situation in which analysts need to work only with cohorts rather than with full datasets. The section closes with a discussion of the importance of validation studies, initially and continuously, to get and maintain the buy-in of data analysts and data users.

Computing Capacity

Data synthesis and privacy assurance, especially for large and complex datasets, can be computationally intensive. This is especially true for large datasets with many variables and many transactions. One should not underestimate this because the synthesis process can take a long time otherwise. While arguably it is only a matter of time before this problem is solved, there are also some structural issues to consider.

For example, when using decision trees for data synthesis, the number of categories in a data field can be a problem. Decision trees select variables and perform binary splits on them to build the tree. For nominal variables these algorithms evaluate all possible splits. For example, if a variable has three possible values {A, B, C}, then the possible splits are {{A},{B,C}}, {{A,B},{C}}, or {{A,C},{B}}. Each of these is evaluated to find the best split. When there are many categories, the number of possible splits can be very large and computationally infeasible to perform. In such cases, special manipulations of the data during pre-processing are needed to enable the synthesis process to proceed.

These are just some of the practical issues that must be considered during the synthesis process. As you synthesize data, there will be more added to this list depending on the types of data that you are working with.

A Toolbox of Techniques

There are multiple methods that can be used for data synthesis. Some methods are best suited to smaller datasets, whereas others will work well only when the datasets are large and can train a deep learning model. Also, some methods will be better suited to cross-sectional data, and for longitudinal data various approaches can be used, depending on the degree of complexity of the longitudinal sequences.

In practice, unless an organization’s datasets are homogeneous, they will need to have a toolbox of synthesizers, with each suited to particular data characteristics. Heuristics can be applied manually or in an automated manner to select the most suitable synthesizer for a particular dataset. Assuming that there is a singular unicorn synthesizer is not going to be the most prudent way to approach the building of data synthesis capacity.

Synthesizing Cohorts Versus Full Datasets

As a practical matter, many data analyses and AIML models are performed or developed, respectively, on specific cohorts or subsets of the full dataset. For example, only a subset of consumers within a specific age range may be of interest or only a subset of the variables. Then that cohort is extracted from the master dataset and sent to the analysts.

For data synthesis, it is much easier to synthesize the full dataset than to synthesize each cohort as it is extracted. The data utility will generally be higher that way, and there is no obvious advantage to the synthesis of individual cohorts.

Given this argument, it is recommended that the data be synthesized as it is coming in rather than as it is going out. For example, if an organization has a data lake and is extracting cohorts from that for specific analyses, then the data synthesis should be performed when the data is going into the data lake such that the data lake consists of only synthetic data.

Continuous Data Feeds

We often see continuous data feeds that need to be synthesized. The common approach is to batch the incoming data, train or update a model with the new data, and then generate a new sequence. Since training does take time, retraining may not have to be performed if there are response-time constraints on the data feeds. In such a case, data can be synthesized using existing models with only periodic updates.

Privacy Assurance as Certification

In the current regulatory environment and with contemporary public discourse that is heavily focused on privacy risks, a prudent organization will err on the conservative side. Regulators’ and the public’s concerns about privacy risks and the increasingly negative narrative on the secondary uses of data mean that it is important for organizations to perform privacy assurance on their synthetic data. As noted before, it should not be taken for granted that the synthesis models were not overfit—that is an empirical question.

There are a few reasons that regular privacy assurance on synthetic data is important:

It provides the documentation necessary to demonstrate that the identification risks are very small. Such documentation may become helpful if questions are raised about the uses of secondary data.

It provides assurance to the data provider that the synthesis process was done well and that the synthesis model did not overfit to the original data.

It demonstrates to the public a level of due diligence when using data for secondary purposes.

Therefore, as a matter of practice, organizations performing data synthesis should consider incorporating privacy assurance as a standard part of the synthesis workflow.

Performing Validation Studies to Get Buy-In

Perhaps the key factor in the success of data synthesis projects is getting the buy-in of the data users and data analysts. In many instances, the use of synthetic data is new for data analysts, for example. Including validation steps in the process of deploying data synthesis will be important, and we have included that explicitly in the process illustrated in Figure 2-14. Validation means that a number of case studies are performed to demonstrate the utility of the synthetic data for the task at hand. Even if case studies exist in other organizations, demonstrations on an organization’s own data can be much more impactful for the data analysts using the synthetic data.

A validation means showing that the results from the synthetic data are similar to the results from the real data. The extent of the similarity will depend on the specific use case. For example, if the use case is to use synthetic data for software testing, then the criteria for similarity would be less stringent than if the data will be used to build an AIML model to identify high-risk insurance claims.

Such validation studies should be chosen to be representative of the datasets and situations that are likely going to be encountered in practice. Choosing the most challenging dataset or context for a validation is not going to be very informative and increases the chances of unsuccessful outcomes. Going in the other direction and choosing the simplest scenarios may not be convincing for the eventual synthetic data users.

Motivated Intruder Tests

Another approach to perform privacy assurance is to organize an attack on the synthetic data to empirically test the extent to which a synthetic record can be mapped to a real person. These are typically called motivated intruder tests in the privacy community.

A motivated intruder test mimics the behavior of an adversary who may attempt to identify synthetic data (with some constraints, such as no criminal or unethical behavior). The individual or team performing such a test should be independent of the team that performed the synthesis.

For a motivated intruder test to be effective, there must be a meaningful way to verify a suspected match of a synthetic record with a real person. Since that is not going to be possible with synthetic data, the limitation of this type of test is that it will result only in suspected matches with no ability to verify them.

Who Owns Synthetic Data?

We decided to leave the most controversial question to the end of the last chapter. The question here is who owns synthetic data. Let’s say that an insurance company owns a particular claims dataset. If a vendor creates a synthetic variant of that dataset, is the synthetic data still owned by the insurance company?

Part of the answer to this question will depend on the contracts that are in place. Since many existing contracts would not have contemplated data synthesis, it is likely that this issue was not directly addressed.

Because there is no one-to-one mapping between the synthetic records and the real customers of that insurance company, it is not the same data. However, the inferences that can be drawn from the synthetic data would be similar to those from the original data.

We will leave the answering of this question as an exercise for the reader.

Conclusions

In this chapter we touched upon some of the practical challenges and solutions that can occur in a data synthesis project.

After completing this chapter (assuming that you have read all of the previous ones as well) you will have a good understanding of the basic concepts and techniques behind data synthesis, as well as the use cases for synthesis and the types of problems that it can solve. As important, you should now have an appreciation of the balance between privacy protection and data utility in synthetic data.
