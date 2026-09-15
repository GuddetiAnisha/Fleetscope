"""CSV contracts, normalization and deterministic synthetic fixtures."""
from pathlib import Path
import numpy as np
import pandas as pd

KEYS = ['country', 'category', 'year']
COUNTRIES = {'sweden':'SE','se':'SE','germany':'DE','de':'DE','france':'FR','fr':'FR','poland':'PL','pl':'PL','united kingdom':'GB','uk':'GB','gb':'GB','united states':'US','usa':'US','us':'US'}
CATEGORIES = {'excavator':'Excavators','excavators':'Excavators','genset':'Generators','generators':'Generators','forklift':'Forklifts','forklifts':'Forklifts','wheel loader':'Wheel loaders','wheel loaders':'Wheel loaders'}
CAT_COLUMNS = ['source_id','source_type','geography','year','coverage','granularity','update_frequency','cost_tier','reliability_score']

def required(df, columns):
    missing = set(columns) - set(df.columns)
    if missing:
        raise ValueError(f'Missing columns: {sorted(missing)}')

def catalogue(df):
    required(df, CAT_COLUMNS)
    df = df.copy()
    for c in ['source_id','source_type','geography','granularity','update_frequency','cost_tier']:
        df[c] = df[c].astype('string').str.strip()
        if df[c].isna().any() or df[c].eq('').any():
            raise ValueError(f'{c} must be nonempty')
    if df.source_id.duplicated().any():
        raise ValueError('source_id must be unique')
    for c in ['coverage','reliability_score','year']:
        df[c] = pd.to_numeric(df[c], errors='raise')
        if not np.isfinite(df[c]).all():
            raise ValueError(f'{c} must be finite')
    if not df.coverage.between(0.001,1).all() or not df.reliability_score.between(0,1).all():
        raise ValueError('coverage must be in [0.001,1]; reliability in [0,1]')
    if not (df.year.eq(df.year.round()) & df.year.between(1900,2100)).all():
        raise ValueError('year must be an integer between 1900 and 2100')
    if not df.cost_tier.isin(['free','low','medium','high']).all():
        raise ValueError('cost_tier must be free, low, medium or high')
    return df

def clean(df, cat):
    required(df, KEYS + ['source_id','observed_count'])
    df = df.copy()
    df['country'] = df.country.astype('string').str.strip().str.lower().map(COUNTRIES)
    df['category'] = df.category.astype('string').str.strip().str.lower().map(CATEGORIES)
    df['source_id'] = df.source_id.astype('string').str.strip()
    for c in ['year','observed_count']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    reason = pd.Series('', index=df.index)
    invalid = df[KEYS+['source_id','observed_count']].isna().any(axis=1) | ~df.source_id.isin(cat.source_id)
    invalid |= ~np.isfinite(df.observed_count) | (df.observed_count < 0)
    invalid |= ~df.year.between(1900,2100) | df.year.ne(df.year.round())
    reason.loc[invalid] = 'Invalid field, unsupported alias, or unknown source'
    duplicate = df.duplicated(KEYS+['source_id'], keep=False) & ~invalid
    reason.loc[duplicate] = 'Duplicate source/market/category/year; resolve before ingestion'
    rejected = df.loc[reason.ne('')].copy()
    rejected['reason'] = reason[reason.ne('')]
    accepted = df.loc[reason.eq('')].copy()
    accepted['year'] = accepted.year.astype(int)
    return accepted, rejected

def generate(directory, seed=42):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    specs = [('registry','Public-style registry',.83,.92,'free'),('survey','Industry-style survey',.52,.80,'medium'),('listings','Marketplace-style listings',.24,.55,'low'),('trade','Trade-model proxy',.65,.72,'high'),('service','Service-network-style sample',.39,.76,'medium')]
    cat = pd.DataFrame([dict(source_id=s,source_type=t,geography='SE;DE;FR;PL;GB;US',year=2025,coverage=c,granularity='country/category/year',update_frequency='annual',cost_tier=cost,reliability_score=r) for s,t,c,r,cost in specs])
    rows, reference, cohorts = [], [], []
    for ci,country in enumerate(['SE','DE','FR','PL','GB','US']):
        for ki,category in enumerate(['Excavators','Generators','Forklifts','Wheel loaders']):
            for year in [2023,2024,2025]:
                truth = round((10000+ci*9000)*(1+ki*.37)*1.025**(year-2023))
                reference.append(dict(country=country,category=category,year=year,reference_count=truth))
                for s,t,coverage,reliability,cost in specs:
                    noise = rng.normal(1,(1-reliability)*.25)
                    bias = 1.85 if (s=='listings' and country=='DE' and category=='Excavators') else 1
                    rows.append(dict(country=country,category=category,year=year,source_id=s,observed_count=round(truth*coverage*noise*bias)))
            for age in range(26):
                cohorts.append(dict(country=country,category=category,cohort_year=2025-age,units=round((10000+ci*9000)*(1+ki*.37)/14*rng.uniform(.8,1.2))))
    cat.to_csv(directory/'sources.csv',index=False)
    pd.DataFrame(rows).to_csv(directory/'observations.csv',index=False)
    pd.DataFrame(reference).to_csv(directory/'benchmark.csv',index=False)
    pd.DataFrame(cohorts).to_csv(directory/'cohorts.csv',index=False)

if __name__ == '__main__':
    generate(Path(__file__).resolve().parents[1]/'data')
