// ============================================================
// FinSight 360 — Power Query M Transformations
// ============================================================
// Apply these in Power BI → Transform Data → Advanced Editor
// for each table listed below.
// ============================================================


// ============================================================
// 1. ml_customer_segments — Cluster Rename to Business Names
// ============================================================
// Purpose: Replace generic cluster labels ("Cluster X (General)")
//          with business-friendly segment names.
//
// Source: data/output/customer_segments.csv
// ============================================================

let
    Source = Csv.Document(
        File.Contents("D:\credit analytics\data\output\customer_segments.csv"),
        [Delimiter = ",", Columns = 5, Encoding = 65001, QuoteStyle = QuoteStyle.None]
    ),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    ChangedTypes = Table.TransformColumnTypes(PromotedHeaders, {
        {"customer_id", Int64.Type},
        {"cluster_id", Int64.Type},
        {"behavioral_segment", type text},
        {"pca_x", type number},
        {"pca_y", type number}
    }),

    // Add a sort order column for slicers
    AddedSortOrder = Table.AddColumn(ChangedTypes, "segment_sort", each
        if [behavioral_segment] = "Premium Customers" then 1
        else if [behavioral_segment] = "Loyal Customers" then 2
        else if [behavioral_segment] = "Growth Customers" then 3
        else if [behavioral_segment] = "Value Seekers" then 4
        else 5,
        Int64.Type
    )
in
    AddedSortOrder;


// ============================================================
// 2. ml_churn_predictions — Risk Tier Sort Order
// ============================================================
// Source: data/output/churn_predictions.csv
// ============================================================

let
    Source = Csv.Document(
        File.Contents("D:\credit analytics\data\output\churn_predictions.csv"),
        [Delimiter = ",", Columns = 6, Encoding = 65001, QuoteStyle = QuoteStyle.None]
    ),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    ChangedTypes = Table.TransformColumnTypes(PromotedHeaders, {
        {"customer_id", Int64.Type},
        {"churn_probability", type number},
        {"churn_risk_tier", type text},
        {"top_risk_driver_1", type text},
        {"top_risk_driver_2", type text},
        {"top_risk_driver_3", type text}
    }),

    // Add sort order for risk tier (High=1, Medium=2, Low=3)
    AddedRiskSort = Table.AddColumn(ChangedTypes, "risk_tier_sort", each
        if [churn_risk_tier] = "High Risk" then 1
        else if [churn_risk_tier] = "Medium Risk" then 2
        else 3,
        Int64.Type
    ),

    // Map technical feature names to readable labels for SHAP drivers
    DriverDisplayNames = {
        {"total_trans_ct_12m", "Low Transaction Count"},
        {"total_trans_amt_12m", "Declining Transaction Value"},
        {"ct_change_q4_q1", "Txn Frequency Drop (Q4/Q1)"},
        {"amt_change_q4_q1", "Spending Decline (Q4/Q1)"},
        {"months_inactive_12m", "Extended Inactivity"},
        {"contacts_count_12m", "High Service Contacts"},
        {"credit_utilization_ratio", "Credit Utilization Stress"},
        {"customer_tenure_months", "Short Tenure"},
        {"total_products_held", "Low Product Holding"},
        {"age", "Age Factor"}
    },

    ReplaceDriver1 = List.Accumulate(
        DriverDisplayNames, AddedRiskSort,
        (state, pair) => Table.ReplaceValue(state, pair{0}, pair{1}, Replacer.ReplaceText, {"top_risk_driver_1"})
    ),
    ReplaceDriver2 = List.Accumulate(
        DriverDisplayNames, ReplaceDriver1,
        (state, pair) => Table.ReplaceValue(state, pair{0}, pair{1}, Replacer.ReplaceText, {"top_risk_driver_2"})
    ),
    ReplaceDriver3 = List.Accumulate(
        DriverDisplayNames, ReplaceDriver2,
        (state, pair) => Table.ReplaceValue(state, pair{0}, pair{1}, Replacer.ReplaceText, {"top_risk_driver_3"})
    )
in
    ReplaceDriver3;


// ============================================================
// 3. shap_feature_importance — Global Importance for Bar Chart
// ============================================================
// Source: data/output/shap_feature_importance.csv
// ============================================================

let
    Source = Csv.Document(
        File.Contents("D:\credit analytics\data\output\shap_feature_importance.csv"),
        [Delimiter = ",", Columns = 4, Encoding = 65001, QuoteStyle = QuoteStyle.None]
    ),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    ChangedTypes = Table.TransformColumnTypes(PromotedHeaders, {
        {"importance_rank", Int64.Type},
        {"feature_name", type text},
        {"display_name", type text},
        {"importance_score", type number}
    })
in
    ChangedTypes;


// ============================================================
// 4. dim_customer — Add Age Band Computed Column
// ============================================================
// Apply this step after connecting to PostgreSQL dim_customer
// ============================================================

// Add this as a Custom Column step in the dim_customer query:

// Table.AddColumn(PreviousStep, "age_band", each
//     if [age] < 30 then "18–29"
//     else if [age] < 40 then "30–39"
//     else if [age] < 50 then "40–49"
//     else if [age] < 60 then "50–59"
//     else "60+",
//     type text
// )

// Also add card category sort order:
// Table.AddColumn(PreviousStep, "card_sort", each
//     if [card_category] = "Platinum" then 1
//     else if [card_category] = "Gold" then 2
//     else if [card_category] = "Silver" then 3
//     else 4,
//     Int64.Type
// )

// ============================================================
// 5. v_customer_clv_predictions — CLV Tier Sort Order
// ============================================================
// Source: PostgreSQL View (v_customer_clv_predictions)
// ============================================================

// Add this as a Custom Column step in the v_customer_clv_predictions query:

// Table.AddColumn(PreviousStep, "clv_tier_sort", each
//     if [clv_tier] = "Platinum" then 1
//     else if [clv_tier] = "Gold" then 2
//     else if [clv_tier] = "Silver" then 3
//     else 4,
//     Int64.Type
// )

// ============================================================
// 6. ml_campaign_propensity â€” Campaign propensity and priority
// ============================================================

let
    Source = Csv.Document(
        File.Contents("D:\credit analytics\data\output\campaign_propensity_scores.csv"),
        [Delimiter = ",", Columns = 9, Encoding = 65001, QuoteStyle = QuoteStyle.None]
    ),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    ChangedTypes = Table.TransformColumnTypes(PromotedHeaders, {
        {"customer_id", Int64.Type},
        {"propensity_score", type number},
        {"propensity_tier", type text},
        {"target_priority_score", type number},
        {"priority_tier", type text},
        {"normalized_clv", type number},
        {"model_version", type text},
        {"prediction_date", type date},
        {"is_synthetic_training", type logical}
    })
in
    ChangedTypes;


// ============================================================
// 7. campaign_experiment_metrics â€” Control vs Treatment summary
// ============================================================

let
    Source = Csv.Document(
        File.Contents("D:\credit analytics\data\output\campaign_experiment_metrics.csv"),
        [Delimiter = ",", Columns = 17, Encoding = 65001, QuoteStyle = QuoteStyle.None]
    ),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    ChangedTypes = Table.TransformColumnTypes(PromotedHeaders, {
        {"experiment_id", type text},
        {"campaign_id", Int64.Type},
        {"campaign_name", type text},
        {"objective", type text},
        {"control_customers", Int64.Type},
        {"treatment_customers", Int64.Type},
        {"control_responses", Int64.Type},
        {"treatment_responses", Int64.Type},
        {"control_conversion_rate", type number},
        {"treatment_conversion_rate", type number},
        {"absolute_lift", type number},
        {"relative_lift", type number},
        {"z_statistic", type number},
        {"p_value", type number},
        {"confidence_interval_low", type number},
        {"confidence_interval_high", type number},
        {"includes_synthetic_data", type logical},
        {"calculated_at", type datetime}
    })
in
    ChangedTypes;

