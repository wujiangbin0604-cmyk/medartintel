"""One scalar mean/std fitted exclusively on accepted training windows."""
import hashlib
import numpy as np


def fit_train_standardizer(filtered_training,training_ids):
    values=np.asarray(filtered_training,dtype=np.float64)
    if not values.size or not np.isfinite(values).all(): raise ValueError('Invalid training values')
    std=float(values.std(ddof=0))
    if std<1e-12: raise ValueError('Training signal variance is zero')
    identifiers='\n'.join(map(str,training_ids)).encode('utf-8')
    return {'method':'global scalar z-score','mean_mV':float(values.mean()),'std_mV':std,'ddof':0,
            'fit_split':'train','fit_beat_count':len(values),'fit_value_count':int(values.size),
            'training_sample_ids_sha256':hashlib.sha256(identifiers).hexdigest(),
            'formula':'X=(X_filtered-mean_mV)/std_mV','per_beat_rescaling':False,'clipping':False}


def transform(values,parameters):
    return ((np.asarray(values,dtype=np.float64)-parameters['mean_mV'])/parameters['std_mV']).astype(np.float32)
