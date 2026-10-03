from pathlib import Path
import json
import pandas as pd
import plotly.express as px
import streamlit as st
from fleetscope.data import catalogue, clean
from fleetscope.model import estimate, validate, survival, rank_sources
from fleetscope.storage import Store
from fleetscope.reporting import bundle

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='FleetScope',page_icon='🌍',layout='wide')
st.title('FleetScope')
st.caption('Multi-Source Industrial Equipment Population Intelligence Platform')
st.info('Synthetic demonstration • Generic equipment markets • No manufacturer or proprietary data')

def sample_path(filename):
    nested = ROOT/'data'/filename
    return nested if nested.exists() else ROOT/filename

def csv_input(label, filename):
    upload = st.sidebar.file_uploader(label,type=['csv'],key=filename)
    return pd.read_csv(upload if upload is not None else sample_path(filename))

try:
    st.sidebar.header('CSV inputs')
    raw_sources = csv_input('Source catalogue','sources.csv')
    raw = csv_input('Equipment observations','observations.csv')
    benchmark = csv_input('Synthetic reference','benchmark.csv')
    cohorts = csv_input('Equipment cohorts','cohorts.csv')
    st.sidebar.caption('Downloadable sample CSVs in the Data tab show the input contracts.')
    tabs = st.tabs(['Overview','Sources & scenarios','Validation','Survival','Data','Run history'])
    with tabs[1]:
        st.subheader('Configure the source catalogue')
        edited = st.data_editor(raw_sources,num_rows='dynamic',key='catalogue_editor')
        sources = catalogue(edited)
        st.subheader('Scenario reliability overrides')
        overrides = {r.source_id:st.slider(r.source_id,0.,1.,float(r.reliability_score),.05,key='weight_'+r.source_id) for r in sources.itertuples()}
    accepted, rejected = clean(raw,sources)
    if len(rejected):
        st.warning(f'{len(rejected)} observations quarantined. Inspect the Data tab.')
    if accepted.empty:
        st.error('No valid observations. Correct the input CSVs.')
        st.stop()
    result, contributions = estimate(accepted,sources,overrides)
    baseline, _ = estimate(accepted,sources)
    result['baseline_estimate'] = baseline.estimate
    result['scenario_delta_pct'] = (result.estimate-result.baseline_estimate)/result.baseline_estimate.replace(0,float('nan'))*100
    as_of = st.sidebar.number_input('Assessment year',1900,2100,2025)
    assessment = rank_sources(sources,as_of)
    metrics, validation = {}, pd.DataFrame()
    with tabs[2]:
        st.subheader('Validation against synthetic reference')
        try:
            metrics, validation = validate(result,benchmark)
            st.json(metrics)
            st.plotly_chart(px.scatter(validation,x='reference_count',y='estimate',color='category',hover_data=['country','year']),width='stretch')
            st.dataframe(validation)
        except ValueError as e:
            st.warning(str(e))
        st.caption('MAPE excludes zero references. Interval coverage is the fraction of matched references inside the model interval. Match coverage measures benchmark completeness.')
    with tabs[0]:
        year = st.selectbox('Estimate year',sorted(result.year.unique()),index=len(result.year.unique())-1)
        categories = st.multiselect('Equipment categories',sorted(result.category.unique()),default=sorted(result.category.unique()))
        view = result[(result.year==year)&result.category.isin(categories)]
        a,b,c = st.columns(3)
        a.metric('Estimated equipment',f'{view.estimate.sum():,.0f}')
        b.metric('Market/category cells',len(view))
        c.metric('High disagreement cells',int(view.conflict.sum()))
        st.caption('Model-based 95% uncertainty intervals: heuristic and uncalibrated. Aggregate interval is intentionally not reported because cross-market covariance is unknown.')
        st.plotly_chart(px.bar(view,x='country',y='estimate',color='category',barmode='group',error_y=view.upper-view.estimate,error_y_minus=view.estimate-view.lower),width='stretch')
        st.dataframe(view)
        st.subheader('Source contributions and outliers')
        detail = contributions[(contributions.year==year)&contributions.category.isin(categories)]
        st.dataframe(detail[['country','category','source_id','observed_count','adjusted_count','weight','contribution','deviation_pct','outlier']])
    with tabs[1]:
        st.subheader('Source recommendations')
        st.dataframe(assessment)
        st.caption('Score = 40% reliability + 30% coverage + 20% freshness + 10% affordability. These are configurable prototype policy choices in model.py.')
        st.plotly_chart(px.bar(result,x='country',y='scenario_delta_pct',color='category',facet_col='year',barmode='group'),width='stretch')
    with tabs[3]:
        curve = st.selectbox('Survival curve',['weibull','exponential','fixed'])
        life = st.slider('Service-life scale (years)',1.,40.,15.)
        shape = st.slider('Weibull shape',.2,5.,2.,.1)
        st.caption('Scale is the age at 36.8% survival for Weibull/exponential, and retirement age for fixed life. Cohort units represent original entrants. Curves are assumptions, not fitted estimates.')
        try:
            survivors = survival(cohorts,as_of,curve,life,shape)
            totals = survivors.groupby(['country','category'],as_index=False).estimated_survivors.sum()
            st.dataframe(totals)
            st.line_chart(survivors.groupby('age').survival_probability.mean())
            st.download_button('Download cohort survival',survivors.to_csv(index=False),'survival.csv','text/csv')
        except ValueError as e:
            st.warning(str(e))
    config = dict(model_version='1.0',overrides=overrides,assessment_year=int(as_of),survival_curve=curve,service_life=life,shape=shape)
    with tabs[4]:
        st.subheader('Accepted observations')
        st.dataframe(accepted)
        st.subheader('Quarantine report')
        st.dataframe(rejected)
        st.download_button('Download quarantine',rejected.to_csv(index=False),'quarantine.csv')
        for filename in ['sources.csv','observations.csv','benchmark.csv','cohorts.csv']:
            st.download_button('Sample '+filename,sample_path(filename).read_bytes(),filename,'text/csv')
    store = Store(ROOT/'fleetscope.sqlite')
    with tabs[5]:
        if st.button('Save estimation run'):
            run_id = store.save(config,raw_observations=raw,accepted=accepted,rejected=rejected,sources=sources,benchmark=benchmark,cohorts=cohorts,estimates=result,contributions=contributions,assessment=assessment,validation=validation)
            st.success('Saved run '+run_id)
        history = store.history()
        st.dataframe(history)
        if not history.empty:
            selected = st.selectbox('Inspect saved run',history.id)
            payload = store.load(selected)
            st.download_button('Download complete run snapshot',json.dumps(payload,indent=2),'run-snapshot.json','application/json')
    st.download_button('Download estimates, assessment & validation report ZIP',bundle(result,assessment,validation,metrics,contributions,config),'fleetscope-report.zip','application/zip')
except (ValueError,KeyError,TypeError,pd.errors.ParserError) as e:
    st.error(f'Input error: {e}')
    st.caption('Compare your files with the sample CSVs in the data folder or project root.')
