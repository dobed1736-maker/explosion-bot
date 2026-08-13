# ============================================================
# MODELO LSTM (PyTorch) - EXPLOSION BOT
# ============================================================

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import StandardScaler
import sys
import os

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
            dropout=dropout if num_layers > 1 else 0.0
        )
        
        self.fc = nn.Linear(hidden_size, output_size)
        self.sigmoid = nn.Sigmoid()
    
    def forward(self, x):
        lstm_out, _ = self.lstm(x)
        last_output = lstm_out[:, -1, :]
        output = self.fc(last_output)
        return self.sigmoid(output).squeeze(-1)  # Control estricto de dimensiones


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
    
    def preparar_secuencias(self, df, target_col='target', es_entrenamiento=True):
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
        
        if es_entrenamiento or self.scaler is None:
            self.scaler = StandardScaler()
            data_scaled = self.scaler.fit_transform(data)
        else:
            data_scaled = self.scaler.transform(data)
        
        X_seq, y_seq = [], []
        
        if target_col in df.columns:
            targets = df[target_col].values
            for i in range(self.sequence_length, len(data_scaled)):
                X_seq.append(data_scaled[i-self.sequence_length:i])
                y_seq.append(targets[i])
            return np.array(X_seq, dtype=np.float32), np.array(y_seq, dtype=np.float32)
        else:
            for i in range(self.sequence_length, len(data_scaled)):
                X_seq.append(data_scaled[i-self.sequence_length:i])
            return np.array(X_seq, dtype=np.float32), None
    
    def entrenar(self, df, target_col='target', epochs=30, batch_size=32):
        print("\n" + "="*50)
        print("🧠 ENTRENANDO LSTM (PyTorch)")
        print("="*50)
        
        X, y = self.preparar_secuencias(df, target_col, es_entrenamiento=True)
        
        print(f"📊 Secuencias generadas: {len(X)}")
        print(f"📊 Features de entrada: {self.input_size}")
        
        if len(X) == 0:
            print("❌ No hay suficientes datos para entrenar la LSTM")
            return None
        
        split = int(len(X) * 0.8)
        X_train, X_val = X[:split], X[split:]
        y_train, y_val = y[:split], y[split:]
        
        X_train_t, y_train_t = torch.tensor(X_train), torch.tensor(y_train)
        X_val_t, y_val_t = torch.tensor(X_val), torch.tensor(y_val)
        
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
            
            if (epoch + 1) % 10 == 0 or epoch == epochs - 1:
                self.modelo.eval()
                with torch.no_grad():
                    val_pred = self.modelo(X_val_t)
                    val_loss = criterion(val_pred, y_val_t)
                    val_acc = ((val_pred > 0.5).float() == y_val_t).float().mean()
                print(f"   Epoch {epoch+1}/{epochs} - Loss: {epoch_loss/len(train_loader):.4f} - Val Loss: {val_loss:.4f} - Val Acc: {val_acc:.2%}")
                self.modelo.train()
        
        print("✅ LSTM entrenado correctamente")
        return self.modelo
    
    def predecir(self, df):
        if self.modelo is None:
            print("❌ Modelo LSTM no cargado/entrenado")
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
        
        if len(data) < self.sequence_length:
            return None
            
        if self.scaler is not None:
            data_scaled = self.scaler.transform(data)
        else:
            print("⚠️ Advertencia: No hay Scaler guardado. Usando datos sin normalizar.")
            data_scaled = data
        
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
        self.modelo.eval()  # Poner explícitamente en modo evaluación tras la carga
        
        print(f"✅ LSTM cargado exitosamente desde: {ruta}")
        return True