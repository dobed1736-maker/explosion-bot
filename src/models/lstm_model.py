# ============================================================
# MODELO LSTM (PyTorch) - EXPLOSION BOT
# ============================================================

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import sys
import os
import joblib

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config.settings import UMBRAL_COMPRA


class LSTMModel(nn.Module):
    """
    Red LSTM para predecir explosiones basado en secuencias
    """
    
    def __init__(self, input_size, hidden_size=64, num_layers=2, output_size=1, dropout=0.2):
        super(LSTMModel, self).__init__()
        
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout
        )
        
        self.fc = nn.Linear(hidden_size, output_size)
        self.sigmoid = nn.Sigmoid()
    
    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        last_output = lstm_out[:, -1, :]
        output = self.fc(last_output)
        return self.sigmoid(output).squeeze()


class ModeloLSTM:
    """
    Wrapper para el modelo LSTM
    """
    
    def __init__(self):
        self.modelo = None
        self.input_size = None
        self.hidden_size = 64
        self.num_layers = 2
        self.umbral = UMBRAL_COMPRA
        self.scaler = None
        self.sequence_length = 30
    
    def preparar_secuencias(self, df, target_col='target'):
        features = [
            'rsi', 'atr', 'bb_ancho', 'bb_porcentaje',
            'macd', 'macd_signal', 'macd_hist',
            'volumen_relativo', 'volumen_aceleracion',
            'taker_buy_ratio', 'retorno_1', 'retorno_5', 
            'retorno_10', 'retorno_15'
        ]
        
        features_existentes = [f for f in features if f in df.columns]
        self.input_size = len(features_existentes)
        
        data = df[features_existentes].values
        targets = df[target_col].values
        
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        data_scaled = scaler.fit_transform(data)
        self.scaler = scaler
        
        X_seq = []
        y_seq = []
        
        for i in range(self.sequence_length, len(data_scaled)):
            X_seq.append(data_scaled[i-self.sequence_length:i])
            y_seq.append(targets[i])
        
        return np.array(X_seq, dtype=np.float32), np.array(y_seq, dtype=np.float32)
    
    def entrenar(self, df, target_col='target', epochs=30, batch_size=32):
        print("\n" + "="*50)
        print("🧠 ENTRENANDO LSTM (PyTorch)")
        print("="*50)
        
        X, y = self.preparar_secuencias(df, target_col)
        
        print(f"📊 Secuencias: {len(X)}")
        print(f"📊 Input size: {self.input_size}")
        
        if len(X) == 0:
            print("❌ No hay suficientes datos para entrenar LSTM")
            return None
        
        split = int(len(X) * 0.8)
        X_train, X_val = X[:split], X[split:]
        y_train, y_val = y[:split], y[split:]
        
        X_train_t = torch.tensor(X_train)
        y_train_t = torch.tensor(y_train)
        X_val_t = torch.tensor(X_val)
        y_val_t = torch.tensor(y_val)
        
        train_dataset = TensorDataset(X_train_t, y_train_t)
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
        
        self.modelo = LSTMModel(
            input_size=self.input_size,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers
        )
        
        optimizer = optim.Adam(self.modelo.parameters(), lr=0.001)
        criterion = nn.BCELoss()
        
        self.modelo.train()
        
        for epoch in range(epochs):
            epoch_loss = 0
            for batch_X, batch_y in train_loader:
                optimizer.zero_grad()
                outputs = self.modelo(batch_X)
                loss = criterion(outputs, batch_y)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
            
            if (epoch + 1) % 10 == 0:
                self.modelo.eval()
                with torch.no_grad():
                    val_pred = self.modelo(X_val_t)
                    val_loss = criterion(val_pred, y_val_t)
                    val_acc = ((val_pred > 0.5).float() == y_val_t).float().mean()
                print(f"   Epoch {epoch+1}/{epochs} - Loss: {epoch_loss/len(train_loader):.4f} - Val Acc: {val_acc:.2%}")
                self.modelo.train()
        
        print("✅ LSTM entrenado correctamente")
        return self.modelo
    
    def predecir(self, df):
        if self.modelo is None:
            print("❌ Modelo LSTM no entrenado")
            return None
        
        features = [
            'rsi', 'atr', 'bb_ancho', 'bb_porcentaje',
            'macd', 'macd_signal', 'macd_hist',
            'volumen_relativo', 'volumen_aceleracion',
            'taker_buy_ratio', 'retorno_1', 'retorno_5', 
            'retorno_10', 'retorno_15'
        ]
        
        features_existentes = [f for f in features if f in df.columns]
        data = df[features_existentes].values
        
        if self.scaler is not None:
            data_scaled = self.scaler.transform(data)
        
        if len(data_scaled) < self.sequence_length:
            return None
        
        X = data_scaled[-self.sequence_length:].reshape(1, self.sequence_length, -1)
        X_t = torch.tensor(X, dtype=torch.float32)
        
        self.modelo.eval()
        with torch.no_grad():
            proba = self.modelo(X_t).item()
        
        return proba
    
    def guardar(self, ruta="models/lstm/lstm_model.pth"):
        if self.modelo is None:
            print("❌ No hay modelo LSTM para guardar")
            return
        
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        
        torch.save({
            'model_state_dict': self.modelo.state_dict(),
            'input_size': self.input_size,
            'hidden_size': self.hidden_size,
            'num_layers': self.num_layers,
            'scaler': self.scaler,
            'sequence_length': self.sequence_length,
            'umbral': self.umbral
        }, ruta, pickle_protocol=4)
        
        print(f"✅ LSTM guardado en: {ruta}")
    
    def cargar(self, ruta="models/lstm/lstm_model.pth"):
        if not os.path.exists(ruta):
            print(f"❌ Archivo LSTM no encontrado: {ruta}")
            return False
        
        checkpoint = torch.load(ruta, weights_only=False)
        
        self.input_size = checkpoint['input_size']
        self.hidden_size = checkpoint['hidden_size']
        self.num_layers = checkpoint['num_layers']
        self.scaler = checkpoint['scaler']
        self.sequence_length = checkpoint['sequence_length']
        self.umbral = checkpoint.get('umbral', 0.7)
        
        self.modelo = LSTMModel(
            input_size=self.input_size,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers
        )
        self.modelo.load_state_dict(checkpoint['model_state_dict'])
        
        print(f"✅ LSTM cargado desde: {ruta}")
        return True


if __name__ == "__main__":
    print("🧪 Probando modelo LSTM...")
    
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
    
    modelo = ModeloLSTM()
    modelo.entrenar(df, epochs=20)
    modelo.guardar()
    
    print("\n✅ Prueba completada")