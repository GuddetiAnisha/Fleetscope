import unittest
import pandas as pd
from real_scb_validation import build_real_validation
from fleetscope.model import estimate, validate

class RealSCBTests(unittest.TestCase):
    def test_temporal_holdout_builder(self):
        rows=[]
        cats=['passenger cars','light lorries','heavy lorries']
        for y in [2020,2021,2022,2023,2024,2025]:
            for c in cats:
                total=1000+(y-2020)*50
                rows.append({'region':'00 Sweden','category':c,'year':y,'count':total})
                for code,share in [('01',.2),('03',.3),('04',.5)]:
                    rows.append({'region':f'{code} county','category':c,'year':y,'count':total*share})
        table=pd.DataFrame(rows)
        sources, obs, bench, meta=build_real_validation(table,2022,2023)
        self.assertEqual(set(bench.year),{2023,2024,2025})
        self.assertTrue(all(sources.coverage.between(.001,1)))
        est,_=estimate(obs,sources)
        metrics,_=validate(est,bench)
        self.assertLess(metrics['MAPE_pct'],1e-6)

if __name__=='__main__':
    unittest.main()
