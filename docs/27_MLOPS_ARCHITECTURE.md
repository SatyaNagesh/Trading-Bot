# QuantLab AI — MLOps Architecture

> **Machine Learning Operations**  
> Version 1.0 | Last Updated: July 2026

---

## Overview

The MLOps framework manages the lifecycle of machine learning models within QuantLab AI — from experimentation to production deployment and monitoring.

---

## ML Pipeline

```
Data ──► Feature Engineering ──► Training ──► Evaluation ──► Deployment ──► Monitoring
  │                              │              │                │
  ▼                              ▼              ▼                ▼
Feature Store              Experiment         Model            Drift
                           Tracking           Registry         Detection
```

---

## Feature Store

### Architecture
```yaml
feature_store:
  storage: PostgreSQL + Qdrant
  online: Redis (low-latency serving)
  
  feature_registry:
    - feature_name
    - feature_type
    - source_data
    - transformation
    - version
    
  serving:
    realtime: < 10ms
    batch: < 5min
```

### Feature Catalog
```yaml
features:
  price_based:
    - open, high, low, close, volume
    - returns (1d, 5d, 21d)
    - volatility (10d, 30d)
    - vwap
  
  technical:
    - sma_10, sma_20, sma_50, sma_200
    - ema_12, ema_26
    - rsi_14
    - macd, macd_signal, macd_histogram
    - bb_upper, bb_lower, bb_width
    - atr_14
  
  market_microstructure:
    - bid_ask_spread
    - order_book_imbalance
    - trade_flow
    - volume_profile
  
  derived:
    - rolling_correlation
    - rolling_sharpe
    - rolling_sortino
    - drawdown
```

---

## Experiment Tracking

```yaml
experiment_tracking:
  tool: MLflow
  
  tracked:
    - Experiment parameters
    - Model architecture
    - Training hyperparameters
    - Evaluation metrics
    - Model artifacts
    - Dataset version
  
  metrics:
    - accuracy / f1_score
    - precision / recall
    - sharpe_ratio
    - mse / mae
    - training_time
    - inference_time
  
  organization:
    - experiment_name
    - run_id
    - tags: [category, author, status]
```

---

## Model Registry

```yaml
model_registry:
  storage: PostgreSQL + S3
  
  stages:
    - development
    - staging
    - production
    - archived
    - deprecated
  
  promotions:
    criteria:
      - Performance thresholds met
      - No regression on benchmarks
      - Drift test passed
      - Human approval received
    
    process:
      development ──► staging (automatic if criteria met)
      staging ──► production (manual approval)
      production ──► archived (when superseded)
```

---

## Model Training Pipeline

```python
# services/ml-engine/train.py
class ModelTrainingPipeline:
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.feature_store = FeatureStore()
        self.experiment_tracker = MLflowTracker()
        
    async def run(self):
        with self.experiment_tracker.start_run():
            # 1. Load features
            features = await self.feature_store.get_features(
                self.config.feature_names,
                self.config.date_range
            )
            
            # 2. Prepare data
            X_train, X_test, y_train, y_test = self.prepare_data(features)
            
            # 3. Train model
            model = self.train_model(X_train, y_train)
            
            # 4. Evaluate
            metrics = self.evaluate(model, X_test, y_test)
            
            # 5. Log everything
            self.experiment_tracker.log_params(self.config)
            self.experiment_tracker.log_metrics(metrics)
            self.experiment_tracker.log_model(model)
            
            return model, metrics
```

---

## Model Deployment

```yaml
model_deployment:
  strategy:
    type: shadow | canary | full
  
  shadow:
    description: "Deploy alongside existing model, no user impact"
    traffic: 0%
    monitoring: Full metrics comparison
  
  canary:
    description: "Gradual traffic shift"
    traffic: 10% → 25% → 50% → 100%
    promotion: Manual at each stage
  
  full:
    description: "Replace existing model entirely"
    traffic: 100%
    rollback: Automatic on performance degradation
```

---

## Monitoring and Drift Detection

```yaml
model_monitoring:
  metrics:
    prediction_drift:
      method: KS-test / PSI
      threshold: p < 0.05
      alert: Slack/Email
    
    feature_drift:
      method: KS-test per feature
      threshold: p < 0.01 (Bonferroni corrected)
      alert: Dashboard warning
    
    performance_decay:
      method: Rolling accuracy / Sharpe
      window: 30 days
      threshold: > 10% degradation
      alert: Critical notification
  
  retraining:
    trigger:
      - Drift detected
      - Performance degradation
      - New data available (monthly)
      - Manual request
```

---

## ML Infrastructure

```yaml
ml_infrastructure:
  training:
    environment: Docker container
    resources:
      cpu: 4 cores
      memory: 16GB
      gpu: Optional (for deep learning)
    
  serving:
    api: FastAPI (inference endpoint)
    resources:
      cpu: 2 cores
      memory: 4GB
    scaling: Horizontal (based on load)
```

---

## Reproducibility

```yaml
reproducibility:
  tracked:
    - Code version (Git commit)
    - Data version (DVC / lakeFS)
    - Feature version
    - Model hyperparameters
    - Training environment (Docker image)
    - Random seed
  
  ensure:
    - Deterministic training
    - Fixed random seeds
    - Consistent data splits
    - Versioned dependencies
```
