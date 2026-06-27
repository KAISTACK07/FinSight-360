# ETL Pipeline & Localization

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
