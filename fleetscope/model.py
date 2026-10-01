"""Explicit model assumptions; no proprietary data or methodology."""
import numpy as np
import pandas as pd
from .data import KEYS, catalogue, required

def estimate(observations, sources, overrides=None, as_of=2025):
    sources = catalogue(sources)
    frame = observations.merge(sources, on='source_id', suffixes=('','_source'), validate='many_to_one')
    if frame.empty:
        raise ValueError('No accepted observations')
    frame['reliability'] = frame.source_id.map(overrides or {}).fillna(frame.reliability_score)
    if not frame.reliability.between(0,1).all():
        raise ValueError('Scenario reliability must be between zero and one')
    frame['adjusted_count'] = frame.observed_count / frame.coverage
    frame['raw_weight'] = frame.reliability * frame.coverage * np.exp(-np.maximum(frame.year-frame.year_source,0)/3)
    records, contributions = [], []
    for key, group in frame.groupby(KEYS):
        g = group.copy()
        if g.raw_weight.sum() <= 0:
            raise ValueError(f'All sources have zero weight for {key}')
        w = g.raw_weight.to_numpy()/g.raw_weight.sum()
        x = g.adjusted_count.to_numpy()
        mean = float(w@x)
        dispersion = float(np.sqrt(w@((x-mean)**2)))
        source_sd = x * (.05+.45*(1-g.reliability.to_numpy())+.20*(1-g.coverage.to_numpy()))
        sd = float(np.sqrt(w@(source_sd**2)+dispersion**2))
        med = np.median(x)
        mad = np.median(np.abs(x-med))
        outlier = np.abs(x-med) > max(3*1.4826*mad,.20*max(med,1))
        conflict = dispersion/max(mean,1)
        records.append(dict(zip(KEYS,key), estimate=mean,lower=max(0,mean-1.96*sd),upper=mean+1.96*sd,source_count=int((w>0).sum()),effective_sources=1/float(w@w),disagreement_cv=conflict,range_ratio=float((x.max()-x.min())/max(mean,1)),conflict=bool(conflict>.20),outliers=int(outlier.sum())))
        g['weight'] = w
        g['contribution'] = w*x
        g['outlier'] = outlier
        g['deviation_pct'] = (x-mean)/max(mean,1)*100
        contributions.append(g)
    return pd.DataFrame(records), pd.concat(contributions,ignore_index=True)

def validate(estimates, benchmark):
    required(benchmark, KEYS+['reference_count'])
    benchmark = benchmark.copy()
    benchmark['reference_count'] = pd.to_numeric(benchmark.reference_count,errors='raise')
    if benchmark.duplicated(KEYS).any() or not np.isfinite(benchmark.reference_count).all() or (benchmark.reference_count<0).any():
        raise ValueError('Benchmark needs unique keys and finite nonnegative reference counts')
    matched = estimates.merge(benchmark,on=KEYS,validate='one_to_one')
    if matched.empty:
        raise ValueError('No benchmark keys match estimates')
    error = matched.estimate-matched.reference_count
    nonzero = matched.reference_count>0
    matched['error'] = error
    matched['covered'] = matched.reference_count.between(matched.lower,matched.upper)
    metrics = dict(MAE=float(error.abs().mean()),RMSE=float(np.sqrt((error**2).mean())),MAPE_pct=float((error[nonzero].abs()/matched.loc[nonzero,'reference_count']).mean()*100) if nonzero.any() else None,interval_coverage=float(matched.covered.mean()),benchmark_match_coverage=len(matched)/len(benchmark),matched_rows=len(matched),zero_reference_rows=int((~nonzero).sum()))
    return metrics, matched

def survival(cohorts, as_of=2025, curve='weibull', service_life=15., shape=2.):
    required(cohorts,['country','category','cohort_year','units'])
    if service_life<=0 or shape<=0 or curve not in ['weibull','exponential','fixed']:
        raise ValueError('Choose a valid curve and positive life/shape')
    result = cohorts.copy()
    for col in ['cohort_year','units']:
        result[col] = pd.to_numeric(result[col],errors='raise')
        if not np.isfinite(result[col]).all():
            raise ValueError('Cohort inputs must be finite')
    if (result.units<0).any() or result.cohort_year.ne(result.cohort_year.round()).any():
        raise ValueError('Invalid units or cohort year')
    result['age'] = as_of-result.cohort_year
    if (result.age<0).any():
        raise ValueError('Cohorts cannot be in the future')
    age = result.age.to_numpy()
    result['survival_probability'] = (age<service_life).astype(float) if curve=='fixed' else np.exp(-(age/service_life)**(shape if curve=='weibull' else 1))
    result['estimated_survivors'] = result.units*result.survival_probability
    return result

def rank_sources(sources, as_of=2025):
    s = catalogue(sources).copy()
    s['freshness'] = np.exp(-np.maximum(as_of-s.year,0)/3)
    s['affordability'] = s.cost_tier.map({'free':1.,'low':.75,'medium':.45,'high':.15})
    s['recommendation_score'] = .4*s.reliability_score+.3*s.coverage+.2*s.freshness+.1*s.affordability
    return s.sort_values('recommendation_score',ascending=False)
