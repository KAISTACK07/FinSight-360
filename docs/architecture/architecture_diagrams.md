# Customer Finance 360° — Architecture Diagrams

This document contains the core architectural diagrams for the Customer Finance 360° Intelligence Platform. These diagrams illustrate the flow of data, the structure of the warehouse, and the integration of machine learning.

*All diagrams are generated using Mermaid.js and will render natively on GitHub.*

---

## 1. Overall Solution Architecture

This diagram illustrates the end-to-end data flow from raw sources to executive dashboards.

```mermaid
graph TD
    A[Data Sources] --> B[ETL Pipeline]
    B --> C[(PostgreSQL Warehouse)]
    C --> D[SQL Analytics Engine]
    D --> E[Machine Learning Models]
    E --> F[Business Validation]
    F --> G[Power BI Dashboards]
    
    classDef database fill:#336791,stroke:#fff,stroke-width:2px,color:#fff;
    class C database;
```

---

## 2. ETL Pipeline & Localization

This diagram shows how raw external datasets are combined, cleaned, and heavily localized to fit the context of an Indian retail bank before being loaded into the warehouse.

```mermaid
graph LR
    A1[BankChurners CSV] --> C[ETL Process]
    A2[Sparkov Behavioral Patterns] --> C
    
    C --> D[Data Cleaning & Joins]
    D --> E[Indian Context Localization]
    E --> F[(PostgreSQL Warehouse)]

    classDef source fill:#f9f9f9,stroke:#333,stroke-width:2px;
    classDef process fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    classDef db fill:#336791,stroke:#fff,stroke-width:2px,color:#fff;
    
    class A1,A2 source;
    class C,D,E process;
    class F db;
```

---

## 3. Star Schema Data Warehouse

The PostgreSQL database is organized into a highly optimized Star Schema, consisting of dimension tables (business entities) and fact tables (business events).

```mermaid
erDiagram
    %% Dimensions
    dim_customer {
        int customer_id PK
        string income_bracket
        string risk_category
    }
    dim_product {
        int product_id PK
        string product_category
    }
    dim_campaign {
        int campaign_id PK
        string target_segment
    }
    dim_date {
        int date_key PK
        int fiscal_year
        boolean is_holiday
    }

    %% Facts
    fact_transactions {
        int transaction_id PK
        int customer_id FK
        int product_id FK
        int date_key FK
        decimal amount
    }
    fact_campaign_responses {
        int response_id PK
        int campaign_id FK
        int customer_id FK
        int date_key FK
        boolean was_accepted
    }
    fact_service_logs {
        int service_id PK
        int customer_id FK
        int date_key FK
        int csat_score
    }

    %% Relationships
    dim_customer ||--o{ fact_transactions : "purchases"
    dim_product ||--o{ fact_transactions : "involves"
    dim_date ||--o{ fact_transactions : "occurs on"

    dim_customer ||--o{ fact_campaign_responses : "responds to"
    dim_campaign ||--o{ fact_campaign_responses : "targeted by"
    dim_date ||--o{ fact_campaign_responses : "recorded on"

    dim_customer ||--o{ fact_service_logs : "initiates"
    dim_date ||--o{ fact_service_logs : "logged on"
```

---

## 4. Machine Learning Pipeline

This diagram maps how historical data from the warehouse is transformed into actionable predictive insights for Power BI.

```mermaid
graph TD
    A[(PostgreSQL Warehouse)] --> B[Feature Engineering]
    
    B --> C[Churn Prediction Model]
    B --> D[Customer Segmentation]
    B --> E[Customer Lifetime Value]
    
    C --> F[SHAP Explainability]
    
    C --> G[Power BI Data Model]
    D --> G
    E --> G
    F --> G

    classDef database fill:#336791,stroke:#fff,stroke-width:2px,color:#fff;
    classDef ml fill:#f3e5f5,stroke:#8e24aa,stroke-width:2px;
    
    class A database;
    class B,C,D,E,F ml;
```
