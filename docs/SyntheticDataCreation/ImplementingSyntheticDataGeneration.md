2. Implementing Data Synthesis | Practical Synthetic Data Generation
Chapter 2. Implementing Data Synthesis

The first decision to be made is whether data synthesis is the best approach for providing data access, compared to alternative privacy-enhancing technologies (PETs). To ensure success with implementing synthesis, it must be aligned with an organization’s priorities. In this chapter we first present a decision framework that will enable the objective selection of data synthesis and help you decide when it will fit business priorities, compared to alternatives.

Once data synthesis is selected as the appropriate solution, we can consider the implementation process.

There are two key components to the implementation of data synthesis at the enterprise level: the process and the structure. The process consists of the key process steps, and demonstrates how to integrate synthesis into a data pipeline. Structure would typically be operationalized through a Synthesis Center of Excellence1 that would have dedicated skills and capacity to generate data for the organization and its customers, as well as provide education and consulting on data synthesis to the rest of the organization. This chapter describes the process and structure in some detail to provide guidance and describe the critical success factors.

In practice, there are many possible scenarios where data synthesis capabilities will need to be deployed. For example, there will be large organizations as well as solo practitioners. Therefore, the following descriptions will need to be tailored to accommodate the specific circumstances.

When to Synthesize

There are many instances in which data synthesis is a better solution to the data-access problem than other methods that can be used. In this section we present a decision framework for choosing among privacy-enhancing technologies (PETs) that can be used to enable data access, including data synthesis.

As we will see, data synthesis is a powerful approach for many situations that optimize business criteria. There will be specific situations where other privacy-enhancing technologies can also work, and we will present these to ensure that the reader selects the best available tools for the task.

Identifiability Spectrum

An important concept that can help unify the thinking around different PETs is the spectrum of identifiability, illustrated in Figure 2-1.

psdg 0201
Figure 2-1. The identifiability spectrum

You can think of identifiability as being a probability of assigning a correct identity to a record in a dataset. Because it is a probability, it varies from 0 to 1. At one end of this spectrum is perfect identifiability, where the probability of assigning a correct identity to a record is one. At the other end is zero identifiability, where it is impossible to assign an identity to a record correctly.

Zero risk is never really achieved—if your aim is zero risk, then all data will have to be treated as personal information. Therefore, discussions of the “impossibility” of identifying a record or the “irreversibility” of a record’s true identity are goals that cannot be attained in practice. In such a case, we are really talking about personal information because zero risk is an impossible standard to meet. Because of that, we will move away from the concept of zero risk and focus on a more pragmatic model.

Any dataset can have a probability of identification along this spectrum (except zero). As you can see in Figure 2-1, along the spectrum there is a threshold value that divides personal information and nonpersonal information or data. When the measured probability in the data is above the threshold, then we have personal information. When the measured probability in the data is at or below the threshold, then we have nonpersonal information.

The PETs that we are interested in place a dataset at a particular point on that spectrum, either above or below the threshold.

This threshold is then also a probability. What should this threshold be? In practice there are a large number of precedents for what this threshold should be in different contexts. We, as a society, have been sharing nonpersonal data for many decades, and there are many examples of organizations around the world that have been setting thresholds and sharing data both publicly and nonpublicly. For example, national statistical agencies such as the Census Bureau in the United States, Statistics Canada in Canada, and the Office of National Statistics in the United Kingdom have been sharing data and using a set of thresholds to do so for a considerable amount of time. And there are others, such as departments of health at the state or provincial levels, large health data custodians, and so on. All this is to say that the choice of a threshold and its interpretation is not very controversial because there are so many precedents that have worked well in practice.

Another key point here is that we are able to measure the probability of identification. There is at least 50 years’ worth of literature in statistical disclosure control on this very topic. Any such measurement of risk is based on a model, and models make assumptions; some are very conservative while others can be very permissive.

Just because the probability of identification is measured does not mean that it is done well or in a reasonable way. Some models, for example, are so permissive that they will be very difficult to defend if something goes wrong. Others are so conservative that they will always inflate the risk. The choice of models does matter.

Trade-Offs in Selecting PETs to Enable Data Access

The traditional trade-off when applying any PET was between privacy protection and data utility. This is illustrated in Figure 2-2. The reasoning was that applying PETs would have a negative impact on data utility because PETs imply that the data is transformed. More transformations to the data means that data quality is being gradually reduced. If you wanted a higher level of privacy, then you would pay for this by having a lower level of utility.

Maximum utility would be the original data without any transformations or controls. But the original data, assuming that it is personal information, will have the minimum amount of privacy. Similarly, maximum privacy is attained when the data is not used or disclosed, which is the minimal utility. Both of these extremes are undesirable.

psdg 0202
Figure 2-2. The trade-off between data privacy and data utility

Therefore, PETs needed to solve an optimization problem by finding the best point on that curve that would achieve a balance between data privacy and data utility, as illustrated in Figure 2-3. Good privacy-enhancing technology solutions would find a point somewhere along the midpoint on that curve that would simultaneously be below the threshold and result in good data utility. The choice of technology was therefore very important to ensure that an organization was operating as close to the threshold as possible to maximize data utility.

psdg 0203
Figure 2-3. The optimal point along the curve is just above the threshold

In addition to data transformations, various controls are sometimes required from the data processors (see Figure 2-4). Controls would be a series of security and privacy practices that are used to manage the overall risk. Therefore, the probability of identification was a function of both data transformations and the controls put into place. Various models were developed to simultaneously assess the risk from the data and the controls.

The advantage of this approach is that you do not need as many data transformations. Because there is a second lever to manage risks, putting in place security and privacy controls was another way to move to a lower probability on that identifiability spectrum. This allows an organization to get closer to the threshold and maximize data utility. So what we have effectively done here is move the line so that at the same level of privacy protection, a higher level of data utility can be achieved.

In general, regulators in many jurisdictions have been open to the concept of managing risk through a combination of data transformations and controls. However, the acceptance has not been universal because there is still some doubt that organizations will truly implement the controls required and maintain them. And that is a big challenge—maintaining trust. Being able to use controls as a mechanism to manage identifiability works in practice only if there is a high level of trust and/or if there is a reliable audit process to ensure that these controls are really in place. Regarding the former, we are on shaky ground, and regarding the latter, it has an impact on the economics of applying a particular approach.

psdg 0204
Figure 2-4. Data transformations and controls are sometimes proposed to ensure that the identifiability risk is below the threshold

Decision Criteria

Practically speaking, organizations do not make decisions about which PETs to deploy based only on the balance between data privacy and data utility. There are typically four main factors that are taken into account, as illustrated in Figure 2-5:

The extent of privacy protection (and the extent to which that is compliant with contemporary regulations). This comes down to whether the threshold is acceptable and if the measured risk is below the threshold.

The extent to which the data utility achieves the business objectives. Maximizing data utility is not a universal objective. For example, nonpersonal data used for software testing may have a lower data utility than a dataset that is used by data scientists to drive innovation around clinical trial recruitment. Therefore, there are different degrees of acceptable data utility. An alternative example could be a company that is required by regulation to make its nonpersonal data available to third parties. Such a company may not want to emphasize data utility because it does not perceive that it would benefit from the data sharing.

Cost is also very important. There are two types of costs. The first is implementation cost, which is the cost of implementing the PETs, say through pseudonymization. These costs will vary greatly depending on the vendor. The second type of cost is operational cost. This is the cost of maintaining the infrastructure and controls to process the data after it has gone through the PET.

The final factor is consumer trust. This will influence whether the consumers (defined here to mean, for example, customers or patients, or even the general public in the case of a government entity) will want to continue to transact with a particular organization. In a healthcare context, it is known that when patients are concerned about how their information will be used, they adopt privacy-preserving behaviors such as not seeking care, self-treating or self-medicating, or omitting vital details in their interactions with their physicians. There is also some evidence that lack of trust in health IT products is slowing their adoption, despite data that supports the benefits of adopting such technology. According to one recent survey from Kantar, the lack of confidence in the privacy and security of health technology platforms has an impact on adoption. Consequently, organizations want to use the best available PETs to ensure that they maintain this public trust.

psdg 0205
Figure 2-5. Organizations use four criteria to decide on the specific PETs to use

PETs Considered

Let’s take a look at the two other PETs and compare them to data synthesis on the data transformations and controls dimensions. More details on secure-multiparty computation can be found in “Secure Multiparty Computation.”

Pseudonymization is the first PET we will examine. Organizations that transform only the direct identifiers in their data are using pseudonymization. These direct identifiers are things like names and Social Security numbers, for example. The resulting datasets would have a higher identifiability than any reasonable threshold. Unfortunately, it remains a common (incorrect) belief that pseudonymous information is no longer personal information—that the identifiability is below the threshold.

The HIPAA limited dataset (LDS) also masks only direct identifiers. The LDS allows HIPAA-covered entities to share this pseudonymized data without patient consent (or authorization) for limited purposes such as research, public health, and healthcare operations. The additional control required under the LDS provision is a data-sharing agreement with the data recipient that should ensure, among other things, that the data will not be re-identified, will not be used to contact individuals, and that the obligations will be passed on to subcontractors. Also, because this is still considered personal information, the security provisions under the HIPAA Security Rule would still apply. This means that there is a layer of security controls that must accompany the LDS. The main advantage for an LDS then is avoiding the obligation to obtain consent, but it is not considered to have an identifiability below the threshold.

Under the GDPR, pseudonymous data includes the requirement that additional information that can be used to identify individuals is kept separately and is subject to technical and organizational measures to ensure that it cannot be used in such a way. Also, because pseudonymous data remains personal information, appropriate controls are needed to process the data. The main advantage to using pseudonymization under the GDPR is to reduce the extent of controls required.

Let’s consider de-identification. There are a number of different methods that fall under the label of de-identification, which we will discuss.

The HIPAA Safe Harbor method involves removing or generalizing a fixed set of attributes. There are some provisions in Safe Harbor that expand its scope somewhat. For example, one attribute is “any other uniquely identifying number, characteristic or code,” which can be interpreted broadly. Also, the covered entity must have no actual knowledge that the remaining information could be used to identify the patient. In practice, these last two items have been applied very lightly, if at all.

It is acknowledged in the disclosure control community that Safe Harbor is not a very strong de-identification standard, and it is not generally recommended. However, for a HIPAA-covered entity, applying that standard provides a straightforward way for that box to be checked and for the data to be declared de-identified. Also, the Safe Harbor standard has been copied in various ways globally. It is attractive because it is very simple to understand and apply. However, strictly speaking, the standard applies only to HIPAA-covered entities and its empirical basis is grounded in analyses performed on US census data. Therefore, the international application of Safe Harbor is questionable.

Risk-based de-identification methods combine statistical methods for measuring the probability of identification and the application of robust controls to further manage the risk of identifiability.

You can see in Figure 2-6 how the three classes of PETs map to the transformation and control dimensions. For example, LDS and GDPR pseudonymization both require data transformations as well as some amount of controls (security, privacy, and/or contractual) to be in place. Fully synthetic data makes minimal demands in terms of controls.

psdg 0206
Figure 2-6. Mapping the different classes of PETs on the transformation and control dimensions to see how these trade off

There is of course a trade-off between cost and data utility. For example, implementing a high level of controls entails higher operational costs. This cost becomes more acceptable when the data utility achieved is also high (assuming that data utility is a priority to the organization). Of course, the ideal is when there is low operational cost and high data utility. While this is perhaps a simple view, Figure 2-7 illustrates some important trade-offs that an organization can make.

Higher controls increases the operational cost of a particular PET. More data transformations reduces the data utility. The ideal quadrant is minimal cost and maximum utility, which is the lower left quadrant. The worst quadrant is the top right one, where the operational costs are high and utility is low.

psdg 0207
Figure 2-7. The trade-offs between adding controls versus using transformations to manage identifiability

Decision Framework

Figure 2-8 illustrates a model that allows us to select the appropriate PET given the key drivers.

In the first column are the weights assigned to each of the four criteria by the organization. A weight is a value between 0 and 1 to indicate how important a particular criterion is. A higher weight means that it is more important. The weights should reflect an organization’s priorities, culture, and risk tolerance.

psdg 0208
Figure 2-8. The decision framework template for evaluating different PETs

Figure 2-9 contrasts two organizations with very different priorities. On the left is an organization that values privacy protection but is cost-sensitive. In that case, the operational costs will be a factor in its decision making. On the right is an organization that is very focused on utility and that is also very cost-sensitive. In these two examples, trust was scored low. Of course, every organization can make its own trade-offs and can change them over time.

psdg 0209
Figure 2-9. A spider diagram can be used to illustrate the trade-offs made by two organizations with differing priorities

The second component of our framework in Figure 2-8 is the rankings. This is the middle part of the table. The rankings would be a number between 1 and 6 for each PET on each of the four criteria. A ranking of 1 means that the PET is better able to meet that criterion. The default rankings that we have been using are shown in Figure 2-10, and our rationale follows.

psdg 0210
Figure 2-10. The decision framework with the rankings included

The transform direct identifier option is assumed to have no controls and are therefore a reflection of some current approaches that are arguably not good practice. The other two types of pseudonymization, HIPAA LDS and GDPR pseudo, do require substantial controls, and under the GDPR additional (all applicable) data is subject to access obligations.

We can see that transforming direct identifiers and HIPAA Safe Harbor have the lowest ranking on privacy because they transform a very small subset of the data and require no additional controls. But they are also the two with the lowest operational costs.

On the trust dimension, data anonymization techniques have been getting negative press recently, and this has eroded consumer trust and raised regulator concerns—hence its ranking. The other methods are not seen as PETs that can guarantee that identifiability is below the threshold.

The score at the bottom is a normalized sum rank, and it is scaled so that a higher value means that it is an option that better matches the priorities of the organization. We can now go through a few examples.

Examples of Applying the Decision Framework

When all of the priorities have the same ranking as in Figure 2-11, we will see that HIPAA Safe Harbor is the least preferred option, with the lowest score. Data synthesis ranks highest because it provides a good balance for the organization across all PETs.

psdg 0211
Figure 2-11. A decision example in which the organization has no specific preferences on which criterion to optimize on

By changing the weights we can see which PETs make the most sense under different priorities.

For example, if we have an organization that is very focused on cost minimization and utility maximization at the expense of privacy protection, as in Figure 2-12, just transforming the direct identifiers may be the best option, while methods like HIPAA Safe Harbor are also quite attractive. These will provide very weak privacy assurances and may have an impact on consumer trust. However, these are business priorities that are used today, and with these priorities the simple transformation of direct identifiers is a rational decision.

psdg 0212
Figure 2-12. A decision example in which the organization optimizes on cost and utility at the expense of privacy and trust

An organization that puts a lot of weight on trust and privacy, as in Figure 2-13, would select data synthesis as a good solution for data access.

psdg 0213
Figure 2-13. A decision example in which the organization optimizes on privacy and trust

Hence, we have a rational way to model and to understand the choices that are being made. Of course, the implication is that when a particular PET is misaligned with an organization’s priorities, any attempt to implement the misaligned PET is not going to be successful.

Note that this ranking model is based on certain assumptions. Firstly, we assume that the use cases are applicable. For example, if a form of pseudonymization is found to be a preference, but it is not possible to get consent and no real case can be made for legitimate interests under the GDPR, then pseudonymization will not be a viable option. Therefore, the ranking is applicable only when the PETs are true alternatives for a particular use case. The priority given to data utility is affected by what the organization was accustomed to prior to implementing PETs. For example, if analysts within an organization were historically provided with access to raw data, then they will expect high data utility. If, on the other hand, the analysts were not provided access to any data in the past, then having access to data in any form will be seen as a plus. Therefore, the perception of good enough data utility does depend on history.

Now that we have a method for selecting a PET, and (specifically for our purpose) ensuring that data synthesis is aligned with an organization’s priorities and optimizes them, we can examine in more detail the implementation process for data synthesis.

Data Synthesis Projects

Data synthesis projects have some processes that are focused on the generation of synthetic data and the validation of the outputs, and some processes that prepare real data so that it can be synthesized. Validation includes the evaluation of both data utility and privacy assurance. In this section we describe these processes and provide guidance on their application.

Data Synthesis Steps

A general data synthesis process is shown in Figure 2-14. This illustrates the complete process. However, in certain situations and use cases not all of the steps would be needed. We will now go through each of the steps.

psdg 0214
Figure 2-14. The overall data synthesis process3

In cases where synthetic data is generated from real data, we need to start from the real data. The real data may be (a) individual-level datasets (or household-level datasets, depending on the context), (b) aggregated data with summaries and cross-tabulations characterizing the population, or (c) a combination of disaggregated and aggregate data. The real data may be open data or nonpublic data coming from a production system, for example.

The synthesis process itself can be performed using different techniques, such as decision trees, deep learning techniques, and iterative proportional fitting. If real data does not exist, then existing models or simulations can be used for data synthesis. The exact choice will be driven by the specific problem that needs to be solved and the level of data utility that is desired.

In many situations a utility assessment needs to be done. This provides assurance to the data consumers that the data utility is acceptable and helps with building trust in the synthesized data. These utility comparisons can be formalized using various similarity metrics so that they are repeatable and automated.

There are two stages to the utility assessment. The first stage is general-purpose comparisons of parameters calculated from the real and synthetic data—for example, comparisons of distributions and bivariate correlations. These act as a “smoke test” of the synthesis process. The second stage is more workload-aware utility assessments.

Workload-aware utility assessments involve doing analyses on the synthetic data that are similar to the types of analyses that would be performed on the real data if it was available. For example, if the real data would be used to build multivariate prediction models, then utility assessment would examine the relative accuracy of the prediction models built on synthetic datasets.

In cases where the synthetic data pertains to individuals and there are potential privacy concerns, then a privacy assurance assessment should also be performed. Privacy assurance evaluates the extent to which real people can be matched to records in the synthetic data and how easy it would be to learn something new if these matches were correct. There are some frameworks that have been developed to assess this risk empirically.

If the privacy assurance assessment demonstrates that the privacy risks are elevated, then it is necessary to revisit the synthesis process and change some of the parameters. For example, the stopping criterion for training the generative model may need to be adjusted because it was overfit and the synthetic records were quite similar to the real records.

The utility assessment needs to be documented to provide the evidence that the level of utility is acceptable. Data analysts will likely want that utility confidence for the data that they are working on. And for compliance reasons, privacy assurance assessments must also be documented.

In practice, data generation would include utility assessment every time, and therefore they are bundled together as part of the “Data Synthesis Services” component in Figure 2-14. Privacy assurance can be performed across multiple synthesis projects because the results are expected to hold across similar datasets and would apply to the whole generation methodology. Hence that is bundled into a separate “Privacy Assurance Services” component in Figure 2-14.

The activities described previously assume that the input real data is ready to be synthesized. In practice, data preparation will be required before real data can be synthesized. Data preparation is not unique to synthesis projects; however, it is an important step that we need to emphasize.

Data Preparation

When generating synthetic data from real data, as with any data analysis project that starts with real data, there will be a need for data preparation, and this should be accounted for as part of the overall process.

Data preparation includes the following:

Data cleansing to remove errors in the data * Data standardization to ensure that all of the fields are using consistent coding schemes

Data harmonization to ensure the data from multiple sources is mapped to the same data dictionary (for example, all the “age” fields in the data, irrespective of the field name and type, are recognized as an “age” field)

Linking of data from multiple sources—it is not possible to link synthetic data because the generated data does not match real people; therefore, all linking has to happen in advance

With data synthesis, the generated data will reflect any quality challenges of the input data. Data analysis in general requires clean data, and synthesis is a form of analysis; it is easier to cleanse the data before the synthesis process. Messy data can distort the utility assessment process and cause the training of the synthesis models to take longer. Furthermore, as we discuss in the next section with respect to pipelines, data synthesis may happen multiple times for the same real dataset, and therefore it is much easier to have data quality issues addressed before synthesis.

Real data will have certain deterministic characteristics, such as structural zeros (these are zero values in the data where it does not make sense for them to be non-zero, i.e., the zero is not a data collection artifact). For example, five-year-olds cannot get pregnant, and therefore the “pregnancy?” value for someone who is five will always be NULL. Also, body mass index (BMI) is a deterministic calculation derived from height and weight. This means that there is no uncertainty in deriving BMI from height and weight. The data synthesis process needs to capture these characteristics and address them. They can be specified a priori either as a series of rules to be satisfied or as edits applied to the synthetic data after the fact. This way the synthesized data will maintain high logical consistency.

A key consideration when implementing data synthesis is how to integrate it within a data architecture or pipeline. In the next section we address this issue and provide some common pipelines.

The Data Synthesis Pipeline

Understanding the data flows that are bringing in data to the data analysts for their AIML projects is important when deciding where data preparation and data synthesis should be implemented in those data flows. It is easiest to explain this through a few examples. All of these examples represent actual situations that we have seen in a variety of industries (such as healthcare and financial services).

One relatively noncomplex setting is where there is a single production dataset or a single data source. In that case the data flows are simple, as illustrated in Figure 2-15. The analysts receiving the synthetic data can then work on that data internally or share it with external parties.

psdg 0215
Figure 2-15. Synthesizing data from a production environment

There is a more complex situation in which the data source is in a different organization. For example, the data may be coming from a financial institution to an analytics consultancy or analytics vendor. This is illustrated in the data flows in Figure 2-16.

Under these data flows, the data analysts/data consumers are not performing the data synthesis because they do not have authority or the controls to process the real data (which may be, for example, personally identifying financial information). Under contemporary data protection regulations, such as the GDPR, the obligations and risks to process personally identifying information are not trivial. Therefore, if the data analyst/data consumer can avoid these obligations by having the data supplier or a trusted third party perform the data synthesis, that would be preferable.

There are three common scenarios. Scenario (a) is when the data preparation and data synthesis both happen at the data supplier. In scenario (b) a trusted third party performs both tasks, and in scenario (c) the data supplier performs the data preparation and the trusted third party performs the data synthesis. In this context a trusted third party would be an independent entity that has the authority and controls in place to process the real data.

psdg 0216
Figure 2-16. Synthesizing data coming from an external data supplier

The last set of examples of data flows that we will look at is where there are many data sources. These are extensions of the examples that we saw in Figure 2-16. In the first data flow shown in Figure 2-17, the data is synthesized at the source by each of multiple data suppliers. For example, the suppliers may be different banks or different pharmacies sending the synthesized data to an analytics company to be pooled and to build models on. Or a medical software developer may be collecting data centrally from all of its deployed customers, with the synthesis performed at the data supplier. Once the synthesized data reaches the data analysts they can build AIML models without the security and privacy obligations of working with real data.

psdg 0217
Figure 2-17. Synthesizing data coming from multiple external data suppliers

Another data flow with multiple data sources involves using a trusted third party who prepares and synthesizes the data on behalf of all of them. The synthesis may be performed on each individual data supplier’s data, or the data may be pooled first and then the synthesis is performed on the pooled data. The exact setup will depend on the characteristics of the data and the intervals at which the data is arriving at the third party. This is illustrated in Figure 2-18.

psdg 0218
Figure 2-18. Synthesizing data coming from multiple external data suppliers going through a single trusted third party who performs data preparation and synthesis

The final data flow that we will consider, illustrated in Figure 2-19, is a variant of the one we examined earlier in which the data preparation is performed at the source before the data is sent to the trusted third party.

psdg 0219
Figure 2-19. Synthesizing data coming from multiple external data suppliers going through a single trusted third party who performs only synthesis

The exact data flow that would be used in a particular situation will depend on a number of factors:

The number of data sources

The costs and readiness of the data analyst/data consumer to process real data and meet any regulatory obligations

The availability of qualified, trusted third parties to perform these tasks

The ability of data suppliers to implement automated data preparation and data synthesis processes

In large organizations, data synthesis needs to be part of a broader structure that is scalable and that can serve multiple business units and client needs. We present the concept of program management, which supports such scalability, in the next section.

Synthesis Program Management

As data synthesis becomes a core part of an organization’s data pipeline, an enterprise-wide structure is needed to ensure that the activities are repeatable and scalable. Scale here can mean data synthesis being used by multiple internal business units or as a capability used by multiple clients. This can be supported at a programmatic level by a Center of Excellence (CoE).

A Synthesis CoE is a mechanism that allows an organization to centralize expertise and technology for the generation of synthetic data. In large organizations such centralization is beneficial because it ensures there is learning over time (a shorter feedback loop), methodologies are standardized across projects and datasets, and economies of scale are enabled with respect to the technologies and computational capacity that may be needed.

A CoE can serve a single organization or a consortium of companies operating in the same space. The end users of the synthetic data can be internal, or the CoE can support clients in implementing, say, analytics tools by making appropriate synthetic data available to them.

The skills needed by those operating the CoE span both technical skills, to generate synthetic data and perform privacy assurance, and business analysis skills, to understand user requirements and translate those into synthesis specifications. More importantly, change management is key because transitioning analysts to using synthetic data will require them to provide some education and possibly a series of utility assessments.

Data synthesis will be a new methodology for many organizations. While the introduction of any data analytics method and technology involves some organizational change, data synthesis introduces some specific considerations during the implementation. In the next section, best practices for the implementation of data synthesis will be discussed to help increase your likelihood of smoothly adopting this approach.

Summary

This chapter provided a decision framework to assess the alignment of data synthesis with an organization’s priorities, followed by the workflows and pipelines that can be used for this implementation. We closed with some practical considerations for program management with synthesis implemented at scale. These three components are important from an enterprise implementation perspective.

After getting this far, you should have a high-level implementation road map and some key elements of a business case for synthesizing data to enable access to data. In the next few chapters we will focus more on the methodology and technology of data synthesis.

1 A Synthesis Center of Excellence is an organizational entity that is responsible for the adoption and sustainability of data synthesis practices and technology within the enterprise.

2 Khaled El Emam et al., “Secure Surveillance of Antimicrobial Resistant Organism Colonization in Ontario Long Term Care Homes” PLoS ONE 9, no. 4 (2014).

3 Copyright Replica Analytics Ltd. Used with permission.
