"""Generate downloadable demo reports without starting the dashboard."""
from pathlib import Path
import json
import pandas as pd
from fleetscope.data import catalogue, clean
from fleetscope.model import estimate, validate, rank_sources, survival
from fleetscope.reporting import bundle

def main():
    root=Path(__file__).resolve().parent
    data=root/'data'
    out=root/'example_reports'
    out.mkdir(exist_ok=True)
    sources=catalogue(pd.read_csv(data/'sources.csv'))
    observations,rejected=clean(pd.read_csv(data/'observations.csv'),sources)
    estimates,contributions=estimate(observations,sources)
    metrics,validation=validate(estimates,pd.read_csv(data/'benchmark.csv'))
    assessment=rank_sources(sources)
    (out/'report.zip').write_bytes(bundle(estimates,assessment,validation,metrics,contributions,{'model_version':'1.0','seed':42,'overrides':{}}))
    (out/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    estimates.to_csv(out/'estimates.csv',index=False)
    survival(pd.read_csv(data/'cohorts.csv')).to_csv(out/'survival.csv',index=False)
    print(json.dumps(metrics,indent=2))

if __name__=='__main__':
    main()
