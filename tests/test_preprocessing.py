import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import numpy as np
import pandas as pd
from src.labels import describe
from src.preprocessing.filters import FilterConfig,filter_continuous
from src.preprocessing.normalization import fit_train_standardizer,transform
from src.preprocessing.extraction import extract_record
from src.preprocessing.splitting import subject_id,lock_subject_split


class PreprocessingTests(unittest.TestCase):
    def test_bandpass_reduces_drift_and_high_frequency_without_passband_phase_delay(self):
        fs=360.; t=np.arange(36000)/fs
        signal=np.sin(2*np.pi*10*t)+.5*np.sin(2*np.pi*60*t)+.8*np.sin(2*np.pi*.1*t)
        filtered,safe=filter_continuous(signal,fs,FilterConfig())
        use=(t>=10)&(t<90)
        def amplitude(freq): return abs(2*np.mean(filtered[use]*np.exp(-2j*np.pi*freq*t[use])))
        self.assertAlmostEqual(amplitude(10),1,delta=.02)
        self.assertLess(amplitude(60),.08)
        self.assertLess(amplitude(.1),.03)
        self.assertTrue(safe[use].all()); self.assertFalse(safe[0])
        self.assertGreater(np.corrcoef(filtered[use],np.sin(2*np.pi*10*t[use]))[0,1],.99)

    def test_nan_gap_is_not_interpolated_and_does_not_poison_whole_record(self):
        fs=100.; values=np.sin(np.arange(10000)/7)
        values[4900:5000]=np.nan
        filtered,safe=filter_continuous(values,fs,FilterConfig())
        self.assertTrue(np.isnan(filtered[4900:5000]).all())
        self.assertTrue(np.isfinite(filtered[1000:4000]).all())
        self.assertFalse(safe[4800]); self.assertFalse(safe[5100]); self.assertTrue(safe[2000])

    def test_normalizer_uses_train_only_and_keeps_extreme_test_values(self):
        train=np.array([[1.,2.,3.],[2.,3.,4.]],dtype=np.float32)
        fitted=fit_train_standardizer(train,['a','b']); snapshot=dict(fitted)
        result=transform(np.array([[1000.,2000.,3000.]]),fitted)
        self.assertEqual(fitted,snapshot); self.assertEqual(fitted['fit_split'],'train')
        self.assertAlmostEqual(transform(train,fitted).mean(),0,places=6)
        self.assertGreater(result.max(),1000)  # no test-dependent clipping

    def test_endpoint_window_is_253_and_non_target_annotations_survive(self):
        fs=360.; signal=np.sin(2*np.pi*8*np.arange(7200)/fs).reshape(-1,1)
        annotations=pd.DataFrame([{'record':'100','annotation_index':i,'sample':s,'time_s':s/fs,'symbol':label,**describe(label)}
                                  for i,(s,label) in enumerate(((100,'N'),(3600,'V'),(5000,'A'),(6000,'+')))])
        record=SimpleNamespace(name='100',fs=fs,signal=signal,digital=(signal*200+1024).astype(int),
                               leads=['MLII'],units=['mV'],annotations=annotations,
                               header=SimpleNamespace(adc_res=[11],adc_zero=[1024]))
        table,values,raw,filtered,indices=extract_record(record,'train','subject_100',FilterConfig())
        self.assertEqual(len(table),4); self.assertEqual(values.shape,(1,253))
        row=table[table.included].iloc[0]
        self.assertEqual(row.annotation_sample,3600); self.assertEqual(row.window_start_sample,3492)
        self.assertEqual(row.window_stop_sample_exclusive,3745); self.assertEqual(row.center_index,108)
        np.testing.assert_array_equal(raw[0],signal[3492:3745,0])
        self.assertEqual(table.iloc[2].exclusion_reason,'not_target_group')
        self.assertEqual(table.iloc[3].exclusion_reason,'non_beat_annotation')

    def test_subject_split_is_locked_and_pair_stays_together(self):
        records=[str(n) for n in range(100,144)]+['200','201','202','234']
        rows=[{'record_id':r,'subject_id':subject_id(r),'annotation_count':1200,
               **{f'{g}_annotation_count':1000 if g=='N' else 200 if g=='V' else 0 for g in ('N','S','V','F','Q')}} for r in records]
        census=pd.DataFrame(rows); manifest=[{'file':'100.dat','sha256':'example_hash'}]
        parent=Path(__file__).resolve().parents[1]/'.test_tmp'; parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as directory:
            path=Path(directory)/'plan.json'
            first,plan=lock_subject_split(census,path,manifest)
            second,_=lock_subject_split(census,path,manifest)
            pd.testing.assert_frame_equal(first,second)
            self.assertEqual(first.subject_id.nunique(),47)
            self.assertEqual(first.groupby('subject_id').split.nunique().max(),1)
            self.assertEqual(first[first.record_id.isin(['100','200'])].split.tolist(),['train','train'])
            with self.assertRaises(ValueError): lock_subject_split(census,path,manifest,seed=10)


if __name__=='__main__': unittest.main()
