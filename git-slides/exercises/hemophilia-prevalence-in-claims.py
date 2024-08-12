# Databricks notebook source
# MAGIC %md
# MAGIC # Estimate Prevalance of Hemophilia in Males using 2021 Commercial Claims
# MAGIC

# COMMAND ----------

# MAGIC %md
# MAGIC ## Setup
# MAGIC
# MAGIC Import functions and CHSD plus data.

# COMMAND ----------

# make more pyspark functions available, such as col() and StructType()

from pyspark.sql.functions import *
from pyspark.sql.types import *

# COMMAND ----------

# consider only males with a full 12 months of enrollment with commercial insurance

commercial_members = spark.read \
    .table("public.chsdplus_2303.outmembermonths_msa") \
    .filter(
      (col("Year") == "2021") &
      (col("LOB") == "COM") &
      (col("Gender") == "M") &
      (col("ExclusionCode").isNull())
    )

males_of_interest = commercial_members \
    .select("MemberID", "Yearmo", "Medical", "Rx") \
    .groupby("MemberID") \
    .agg(sum("medical").alias("sum_medical"), sum("Rx").alias("sum_Rx")) \
    .filter((col("sum_medical") == 12) & (col("sum_Rx") == 12)) \
    .select("MemberID") \
    .distinct()

# COMMAND ----------

# consider only claims for said males, for procedures OTHER THAN those involving Lab or Radiology
# since such claims often code the ICD which they're testing for, not necessarily the ICD present in the patient

mr_line_description = spark.read.table("public.codeset_20222.refmr_line").select(col("MR_LINE").alias("MR_Line"), "MR_LINE_DESC").distinct()
relevant_mrlines = mr_line_description.filter(~col("MR_LINE_DESC").contains("Radiology") & ~col("MR_LINE_DESC").contains("Lab ")).select("MR_Line")

hcpcs_description = spark.read.table("public.codeset_20222.refmr_hcpcs").select(col("PROC").alias("HCPCS"), col("PROC_DESC").alias("HCPCS_description"))
relevant_hcpcs = hcpcs_description.filter(~col("HCPCS_description").contains("Radiology") & ~col("HCPCS_description").contains("Lab ")).select("HCPCS")

commercial_claims = spark.read \
    .table("public.chsdplus_2303.outclaims") \
    .filter(
        (col("Year") == "2021") &
        (col('LOB') == 'COM') &
        (col("ExclusionCode").isNull())
    )

claims_of_interest = commercial_claims \
    .join(males_of_interest, on = "MemberID", how = "inner") \
    .join(relevant_hcpcs, on = "HCPCS", how = "inner") \
    .join(relevant_mrlines, on = "MR_Line", how = "inner") \
    .select("MemberID", "FromDate", commercial_claims.colRegex("`^ICDDiag\d+$`")) \
    .distinct()

claims_of_interest.printSchema()

# COMMAND ----------

# MAGIC %md
# MAGIC ### Hemophiliacs
# MAGIC
# MAGIC Here defined as any male in the cohort who has at lease one occurance of the following ICDs.
# MAGIC
# MAGIC - [D66 is Hemophilia A](https://www.icd10data.com/ICD10CM/Codes/D50-D89/D65-D69/D66-/D66)
# MAGIC - [D67 is Hemophilia B](https://www.icd10data.com/ICD10CM/Codes/D50-D89/D65-D69/D67-/D67)
