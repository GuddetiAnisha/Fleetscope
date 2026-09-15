import io
import zipfile
import numpy as np
import pandas as pd
import pytest
from fleetscope.data import generate, catalogue, clean
from fleetscope.model import estimate, validate, survival, rank_sources
from fleetscope.storage import Store
from fleetscope.reporting import bundle

@pytest.fixture
def sample(tmp_path):
    generate(tmp_path)
    return {name:pd.read_csv(tmp_path/(name+'.csv')) for name in ['sources','observations','benchmark','cohorts']}

def test_end_to_end(sample,tmp_path):
    s=sample
    accepted,rejected=clean(s['observations'],catalogue(s['sources']))
    assert len(accepted)==360 and rejected.empty
    result,detail=estimate(accepted,s['sources'])
    assert len(result)==72
    assert np.allclose(detail.groupby(['country','category','year']).contribution.sum(),result.set_index(['country','category','year']).estimate)
    assert (result.lower<=result.estimate).all() and (result.upper>=result.estimate).all()
    assert detail.outlier.any()
    metrics,validation=validate(result,s['benchmark'])
    assert metrics['MAPE_pct']<10 and metrics['benchmark_match_coverage']==1
    db=Store(tmp_path/'test.sqlite')
    run=db.save({'seed':42},estimates=result)
    assert len(db.history())==1 and 'estimates' in db.load(run)
    report=bundle(result,rank_sources(s['sources']),validation,metrics,detail,{})
    assert 'validation.csv' in zipfile.ZipFile(io.BytesIO(report)).namelist()

def test_quarantine_and_aliases(sample):
    df=sample['observations'].head(3).copy()
    df.loc[0,'country']=' Sweden '
    df.loc[0,'category']='excavator'
    df.loc[1,'observed_count']=-1
    df.loc[2,'country']='unknown'
    good,bad=clean(df,sample['sources'])
    assert len(good)==1 and good.iloc[0].country=='SE' and len(bad)==2
    good,bad=clean(pd.concat([df.head(1)]*2),sample['sources'])
    assert good.empty and len(bad)==2

def test_weights_and_interval_disagreement(sample):
    obs=sample['observations'].head(5).copy()
    sources=sample['sources']
    obs['observed_count']=sources.coverage.to_numpy()*1000
    base,_=estimate(obs,sources)
    assert base.estimate.iloc[0]==pytest.approx(1000)
    obs.loc[0,'observed_count']*=3
    changed,_=estimate(obs,sources)
    assert changed.disagreement_cv.iloc[0]>base.disagreement_cv.iloc[0]
    assert changed.upper.iloc[0]-changed.lower.iloc[0]>base.upper.iloc[0]-base.lower.iloc[0]
    excluded,_=estimate(obs,sources,{'registry':0})
    assert excluded.estimate.iloc[0]==pytest.approx(1000)
    with pytest.raises(ValueError): estimate(obs,sources,dict.fromkeys(sources.source_id,0))

def test_survival(sample):
    for curve in ['weibull','fixed','exponential']:
        a=survival(sample['cohorts'],curve=curve,service_life=10)
        b=survival(sample['cohorts'],curve=curve,service_life=20)
        assert b.estimated_survivors.sum()>=a.estimated_survivors.sum()
        assert a.survival_probability.between(0,1).all()
    with pytest.raises(ValueError): survival(sample['cohorts'],as_of=2020)

def test_invalid_catalogue(sample):
    s=sample['sources'].copy()
    s.loc[0,'coverage']=0
    with pytest.raises(ValueError): catalogue(s)

def test_zero_reference(sample):
    result,_=estimate(sample['observations'],sample['sources'])
    benchmark=sample['benchmark'].copy()
    benchmark['reference_count']=0
    metrics,_=validate(result,benchmark)
    assert metrics['MAPE_pct'] is None and metrics['zero_reference_rows']==72
