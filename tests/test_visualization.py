import unittest
from types import SimpleNamespace
import numpy as np
import pandas as pd
from src.heartbeat import extract_heartbeats,window_features,stratified_sample_indices
from src.labels import describe
from src.visuals.quality import baseline_windows


def synthetic_record(name):
    annotations=pd.DataFrame([{'record':name,'annotation_index':i,'sample':sample,'time_s':sample/10,
                               'symbol':symbol,**describe(symbol)}
                              for i,(sample,symbol) in enumerate(zip((0,5,19),('N','A','V')))])
    return SimpleNamespace(name=name,fs=10.,leads=['MLII'],units=['mV'],
                           signal=np.arange(20,dtype=float).reshape(-1,1)/10,annotations=annotations)


class VisualizationTests(unittest.TestCase):
    def test_energy_uses_physical_sample_interval(self):
        features=window_features(np.array([[0.,1.,-1.],[3.,4.,2.]]),fs=2.)
        np.testing.assert_allclose(features['peak_to_peak'],[2,2])
        np.testing.assert_allclose(features['energy_raw'],[1,14.5])
        np.testing.assert_allclose(features['energy_centered'],[1,1])

    def test_extraction_keeps_counts_and_exact_samples(self):
        record=synthetic_record('100')
        table,collections=extract_heartbeats([record],pre_s=.2,post_s=.3)
        self.assertEqual(len(table),3)
        self.assertEqual(table.extraction_status.tolist(),['left','valid','right'])
        np.testing.assert_array_equal(collections['MLII'].raw[0],record.signal[3:9,0])
        self.assertEqual(collections['MLII'].metadata.beat_id.tolist(),['100:1'])

    def test_rr_never_crosses_record_boundary(self):
        table,_=extract_heartbeats([synthetic_record('100'),synthetic_record('200')],.2,.3)
        self.assertTrue(table.groupby('record').head(1).rr_previous_s.isna().all())
        self.assertTrue(table.groupby('record').tail(1).rr_next_s.isna().all())
        np.testing.assert_allclose(table.groupby('record').nth(1).rr_previous_s,[.5,.5])

    def test_sampling_keeps_rare_strata_without_duplicates(self):
        metadata=pd.DataFrame({'record':['100']*22+['200']*11,
                               'aami_group':['N']*20+['S']*2+['F']+['V']*10})
        selected=stratified_sample_indices(metadata,42,per_group=5,maximum=10)
        np.testing.assert_array_equal(selected,stratified_sample_indices(metadata,42,5,10))
        self.assertEqual(len(selected),10)
        self.assertEqual(len(np.unique(selected)),10)
        groups=metadata.iloc[selected].aami_group.value_counts()
        self.assertEqual(groups['F'],1); self.assertEqual(groups['S'],2)

    def test_block_median_drift_proxy_is_computed(self):
        record=synthetic_record('100')
        record.signal=np.arange(100,dtype=float).reshape(-1,1)/100
        table=baseline_windows(record)
        self.assertAlmostEqual(table.block_median_range.iloc[0],.9)
        self.assertEqual(table.block_count.iloc[0],10)


if __name__=='__main__':
    unittest.main()
