"""Real-data methodological validation for FleetScope using official Swedish vehicle-register data.

Source: Statistics Sweden (SCB), table TK1001AC:
'Vehicles in use by region and type of vehicles. Year 2002 - 2025.'

The three FleetScope source views are constructed geographic subsets of one
official registry, not independent publishers. Coverage is calibrated only on
historical years and evaluation uses later held-out years.
"""
from __future__ import annotations
from pathlib import Path
import argparse, io, json, re, zipfile
import pandas as pd
import requests

from fleetscope.model import estimate, validate

SCB_BULK_URL = "https://www.statistikdatabasen.scb.se/Resources/PX/bulk/ssd/en/TAB1278_en.zip"

def download_scb(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    zpath = out_dir/'TAB1278_en.zip'
    if not zpath.exists():
        r = requests.get(SCB_BULK_URL, timeout=120)
        r.raise_for_status()
        zpath.write_bytes(r.content)
    with zipfile.ZipFile(zpath) as z:
        csvs = [n for n in z.namelist() if n.lower().endswith('.csv')]
        if not csvs:
            raise RuntimeError('SCB ZIP contains no CSV')
        target = out_dir/'scb_vehicles_in_use.csv'
        target.write_bytes(z.read(csvs[0]))
    return target

def _read_csv(path: Path) -> pd.DataFrame:
    raw = path.read_bytes()
    for enc in ('utf-8-sig','utf-8','latin1'):
        try:
            text = raw.decode(enc)
            for sep in (';',',','\t'):
                df = pd.read_csv(io.StringIO(text), sep=sep)
                if df.shape[1] >= 4:
                    return df
        except Exception:
            pass
    raise RuntimeError('Could not parse SCB CSV')

def _find_col(columns, words):
    norm = {c: re.sub(r'[^a-z0-9]+',' ',str(c).lower()).strip() for c in columns}
    for c,n in norm.items():
        if any(w in n for w in words):
            return c
    return None

def normalize_scb(df: pd.DataFrame) -> pd.DataFrame:
    region = _find_col(df.columns, ['region'])
    vehicle = _find_col(df.columns, ['type of vehicle','vehicle'])
    year = _find_col(df.columns, ['year'])
    value = _find_col(df.columns, ['number','value'])
    if not all([region,vehicle,year,value]):
        raise ValueError(f'Could not identify SCB columns. Found: {list(df.columns)}')
    out = df[[region,vehicle,year,value]].copy()
    out.columns = ['region','category','year','count']
    out['region'] = out.region.astype(str).str.strip()
    out['category'] = out.category.astype(str).str.strip()
    out['year'] = pd.to_numeric(out.year, errors='coerce')
    out['count'] = pd.to_numeric(out['count'].astype(str).str.replace(' ','',regex=False), errors='coerce')
    return out.dropna().assign(year=lambda x:x.year.astype(int))

def build_real_validation(table: pd.DataFrame, calibration_end=2022, eval_start=2023):
    national = table[table.region.str.match(r'^00\b', na=False)].copy()
    counties = table[table.region.str.match(r'^\d{2}\s', na=False) & ~table.region.str.match(r'^00\b', na=False)].copy()
    if national.empty or counties.empty:
        raise ValueError('Expected SCB national and county rows were not found')

    preferred = ['passenger cars','light lorries','heavy lorries','buses','motorcycles']
    available = {c.lower():c for c in national.category.unique()}
    categories = [available[p] for p in preferred if p in available][:4]
    if len(categories) < 3:
        categories = sorted(national.category.unique())[:4]

    national = national[national.category.isin(categories)]
    counties = counties[counties.category.isin(categories)]
    codes = sorted(counties.region.str.extract(r'^(\d{2})')[0].dropna().unique())
    groups = {f'county_group_{i+1}': set(codes[i::3]) for i in range(3)}
    counties['county_code'] = counties.region.str.extract(r'^(\d{2})')[0]

    cal_years = sorted(y for y in national.year.unique() if y <= calibration_end)
    eval_years = sorted(y for y in national.year.unique() if y >= eval_start)
    if not cal_years or not eval_years:
        raise ValueError('Calibration/evaluation years unavailable in table')

    national_sum = national.groupby(['category','year'],as_index=False)['count'].sum()
    source_rows, source_specs = [], []
    for sid, code_set in groups.items():
        subset = counties[counties.county_code.isin(code_set)]
        grouped = subset.groupby(['category','year'],as_index=False)['count'].sum()
        cal = grouped[grouped.year.isin(cal_years)].merge(
            national_sum[national_sum.year.isin(cal_years)],
            on=['category','year'], suffixes=('_partial','_national'))
        coverage = float(cal.count_partial.sum()/cal.count_national.sum())
        coverage = min(max(coverage,0.001),1.0)
        source_specs.append({
            'source_id':sid,'source_type':'SCB county subset','geography':'Sweden counties',
            'year':int(max(cal_years)),'coverage':coverage,'granularity':'country/category/year',
            'update_frequency':'annual','cost_tier':'free','reliability_score':0.95})
        for r in grouped[grouped.year.isin(eval_years)].itertuples():
            source_rows.append({'country':'SE','category':r.category,'year':int(r.year),
                                'source_id':sid,'observed_count':float(r.count)})

    benchmark = national_sum[national_sum.year.isin(eval_years)].rename(columns={'count':'reference_count'})
    benchmark.insert(0,'country','SE')
    return pd.DataFrame(source_specs), pd.DataFrame(source_rows), benchmark, {
        'categories':categories,'calibration_years':cal_years,'evaluation_years':eval_years}

def run(data_dir='real_data', output_dir='results_real_scb', calibration_end=2022, eval_start=2023):
    data_dir, output_dir = Path(data_dir), Path(output_dir)
    csv_path = download_scb(data_dir)
    table = normalize_scb(_read_csv(csv_path))
    sources, observations, benchmark, meta = build_real_validation(table, calibration_end, eval_start)
    estimates, contributions = estimate(observations, sources)
    metrics, matched = validate(estimates, benchmark)

    output_dir.mkdir(parents=True, exist_ok=True)
    sources.to_csv(output_dir/'real_sources.csv', index=False)
    observations.to_csv(output_dir/'real_observations.csv', index=False)
    benchmark.to_csv(output_dir/'real_benchmark.csv', index=False)
    estimates.to_csv(output_dir/'real_estimates.csv', index=False)
    matched.to_csv(output_dir/'real_validation_rows.csv', index=False)
    payload = {
        'dataset':'Statistics Sweden SCB TK1001AC',
        'source_url':SCB_BULK_URL,
        'design':'coverage calibration on historical years; later-year holdout evaluation',
        'independence_warning':'Source views are geographic subsets of one official registry, not independent publishers.',
        **meta,'metrics':metrics}
    (output_dir/'summary.json').write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(json.dumps(payload, indent=2))
    return payload

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--data-dir',default='real_data')
    p.add_argument('--output-dir',default='results_real_scb')
    p.add_argument('--calibration-end',type=int,default=2022)
    p.add_argument('--eval-start',type=int,default=2023)
    a=p.parse_args()
    run(a.data_dir,a.output_dir,a.calibration_end,a.eval_start)
