"""Small CPU ANN; executable demonstration, never a production hiring claim."""
import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
import json
import numpy as np
from .ml import prepare_training, preprocessor, ARTIFACTS


def run_ann(path):
    import tensorflow as tf
    tf.keras.utils.set_random_seed(42)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.config.threading.set_intra_op_parallelism_threads(1)
    X_train, X_test, y_train, y_test = prepare_training(path)
    prep = preprocessor()
    train = prep.fit_transform(X_train).astype('float32')
    test = prep.transform(X_test).astype('float32')
    model = tf.keras.Sequential([tf.keras.layers.Input(shape=(train.shape[1],)),
        tf.keras.layers.Dense(16, activation='relu'), tf.keras.layers.Dense(8, activation='relu'),
        tf.keras.layers.Dense(1, activation='sigmoid')])
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    # Explicit minibatches avoid platform-specific tf.data worker thread limits.
    labels = y_train.to_numpy(dtype='float32')
    for _ in range(15):
        for start in range(0, len(train), 16):
            model.train_on_batch(train[start:start + 16], labels[start:start + 16])
    probabilities = model(test, training=False).numpy().ravel()
    report = {'input_features': list(X_train.columns), 'encoded_input_width': train.shape[1],
        'target': 'historical selected vs rejected', 'output': 'sigmoid probability',
        'test_accuracy': float(np.mean((probabilities >= .5) == y_test.to_numpy())),
        'sample_probability': float(probabilities[0]), 'limitation': 'Synthetic small dataset; execution proof only.'}
    ARTIFACTS.mkdir(exist_ok=True)
    model.save(ARTIFACTS / 'ann.keras')
    import joblib
    joblib.dump(prep, ARTIFACTS / 'ann_preprocessor.joblib')
    restored = tf.keras.models.load_model(ARTIFACTS / 'ann.keras')
    report['reloaded_probability'] = float(restored(test[:1], training=False).numpy()[0, 0])
    (ARTIFACTS / 'ann_metrics.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report
