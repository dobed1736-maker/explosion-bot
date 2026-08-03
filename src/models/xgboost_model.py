# ============================================================
# MODELO XGBOOST - EXPLOSION BOT
# ============================================================

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import joblib
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import UMBRAL_COMPRA


class ModeloXGBoost:
    """
    Modelo XGBoost para predecir explosiones
    """
    
    def __init__(self):
        self.modelo = None
        self.features = None
        self.umbral = UMBRAL_COMPRA
        self.escalador = None
    
    def preparar_features(self, df):
        """
        Selecciona y prepara las features para el modelo
        """
        # Lista de features a usar
        self.features = [
            'rsi', 'atr', 'bb_ancho', 'bb_porcentaje',
            'macd', 'macd_signal', 'macd_hist',
            'volumen_relativo', 'volumen_aceleracion',
            'taker_buy_ratio', 'retorno_1', 'retorno_5', 
            'retorno_10', 'retorno_15', 'rango'
        ]
        
        # Verificar que todas existan
        features_existentes = []
        for f in self.features:
            if f in df.columns:
                features_existentes.append(f)
            else:
                print(f"⚠️ Feature no encontrada: {f}")
        
        self.features = features_existentes
        
        # Crear X con las features
        X = df[self.features].copy()
        
        # Rellenar NaN
        X = X.fillna(0)
        
        return X
    
    def entrenar(self, df, target_col='target'):
        """
        Entrena el modelo XGBoost
        """
        print("\n" + "="*50)
        print("🧠 ENTRENANDO XGBOOST")
        print("="*50)
        
        # Preparar features
        X = self.preparar_features(df)
        y = df[target_col]
        
        # Eliminar filas con NaN en el target
        mascara = y.notna()
        X = X[mascara]
        y = y[mascara]
        
        print(f"📊 Datos de entrenamiento: {len(X)} filas")
        print(f"📊 Features: {len(self.features)}")
        
        # Verificar balanceo de clases
        total_clase_1 = y.sum()
        total_clase_0 = len(y) - total_clase_1
        print(f"📊 Distribución de clases:")
        print(f"   Clase 0 (no explosión): {total_clase_0}")
        print(f"   Clase 1 (explosión): {total_clase_1}")
        print(f"   Ratio: {total_clase_1/len(y):.2%}")
        
        # Time Series Split (validación temporal)
        tscv = TimeSeriesSplit(n_splits=3)
        
        X_train = None
        X_test = None
        y_train = None
        y_test = None
        
        for train_idx, test_idx in tscv.split(X):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
        
        # Calcular peso para clase minoritaria
        if total_clase_1 > 0:
            scale_pos_weight = total_clase_0 / total_clase_1
        else:
            scale_pos_weight = 1
        
        # Crear modelo
        self.modelo = xgb.XGBClassifier(
            objective='binary:logistic',
            scale_pos_weight=scale_pos_weight,
            n_estimators=150,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            early_stopping_rounds=10
        )
        
        # Entrenar
        self.modelo.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=False
        )
        
        # Evaluar
        y_pred = self.modelo.predict(X_test)
        y_proba = self.modelo.predict_proba(X_test)[:, 1]
        
        print("\n📊 RESULTADOS DEL MODELO:")
        print(f"   Accuracy: {accuracy_score(y_test, y_pred):.2%}")
        
        # Reporte detallado
        print(classification_report(y_test, y_pred))
        
        # Matriz de confusión
        tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
        print(f"\n🎯 Matriz de Confusión:")
        print(f"   Verdaderos Positivos (acertó explosión): {tp}")
        print(f"   Falsos Positivos (falsa alarma): {fp}")
        print(f"   Verdaderos Negativos (acertó calma): {tn}")
        print(f"   Falsos Negativos (no detectó explosión): {fn}")
        
        # Precisión en predicciones positivas
        if tp + fp > 0:
            precision = tp / (tp + fp)
            print(f"   Precisión: {precision:.2%}")
        
        # Recall de explosiones
        if tp + fn > 0:
            recall = tp / (tp + fn)
            print(f"   Recall (detección de explosiones): {recall:.2%}")
        
        return self.modelo
    
    def predecir(self, df):
        """
        Predice la probabilidad de explosión
        """
        if self.modelo is None:
            print("❌ Modelo no entrenado")
            return None
        
        X = self.preparar_features(df)
        X = X.fillna(0)
        
        proba = self.modelo.predict_proba(X)[:, 1]
        return proba
    
    def predecir_ultima(self, df):
        """
        Predice la probabilidad de explosión para la última vela
        """
        if self.modelo is None:
            print("❌ Modelo no entrenado")
            return None
        
        X = self.preparar_features(df)
        X = X.fillna(0)
        
        proba = self.modelo.predict_proba(X)[:, 1]
        return proba[-1] if len(proba) > 0 else 0
    
    def guardar(self, ruta="models/xgboost/xgboost_model.pkl"):
        """
        Guarda el modelo entrenado
        """
        if self.modelo is None:
            print("❌ No hay modelo para guardar")
            return
        
        # Crear directorio si no existe
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        
        data = {
            'modelo': self.modelo,
            'features': self.features,
            'umbral': self.umbral
        }
        joblib.dump(data, ruta)
        print(f"✅ Modelo guardado en: {ruta}")
    
    def cargar(self, ruta="models/xgboost/xgboost_model.pkl"):
        """
        Carga un modelo guardado
        """
        if not os.path.exists(ruta):
            print(f"❌ Archivo no encontrado: {ruta}")
            return False
        
        data = joblib.load(ruta)
        self.modelo = data['modelo']
        self.features = data['features']
        self.umbral = data.get('umbral', 0.7)
        print(f"✅ Modelo cargado desde: {ruta}")
        return True


if __name__ == "__main__":
    print("🧪 Probando modelo XGBoost...")
    
    # Crear datos de prueba
    np.random.seed(42)
    df = pd.DataFrame({
        'close': 100 + np.cumsum(np.random.randn(100) * 0.5),
        'high': 100 + np.cumsum(np.random.randn(100) * 0.5) + 0.5,
        'low': 100 + np.cumsum(np.random.randn(100) * 0.5) - 0.5,
        'volume': np.random.randint(1000, 10000, 100),
        'taker_buy_base_asset_volume': np.random.randint(500, 5000, 100)
    })
    
    from src.features.indicators import calcular_todos_indicadores
    from src.features.target_creator import crear_target_explosion
    
    df = calcular_todos_indicadores(df)
    df = crear_target_explosion(df, umbral=0.05, ventana=12)
    df = df.dropna()
    
    modelo = ModeloXGBoost()
    modelo.entrenar(df)
    modelo.guardar()
    
    print("\n✅ Prueba completada")