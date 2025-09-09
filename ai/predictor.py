# ================== AI MODULE ==================
"""
Yapay zeka modülü - Online logistic regression, özelliklere dayalı öğrenme
"""

import math
from typing import Dict, Any, Optional
from ..config.settings import AI_ENABLED, AI_LR, AI_L2, AI_INIT_BIAS, SCORING_WEIGHTS


class OnlineLogisticRegression:
    """Online Logistic Regression sınıfı"""
    
    def __init__(self, learning_rate: float = AI_LR, l2_reg: float = AI_L2, 
                 init_bias: float = AI_INIT_BIAS):
        self.lr = learning_rate
        self.l2_reg = l2_reg
        
        # Ağırlıkları başlat
        self.weights = {key: 0.0 for key in SCORING_WEIGHTS.keys()}
        self.bias = init_bias
        self.samples_seen = 0
    
    def _sigmoid(self, x: float) -> float:
        """Sigmoid aktivasyon fonksiyonu"""
        return 1.0 / (1.0 + math.exp(-max(-500, min(500, x))))  # Overflow koruması
    
    def predict_proba(self, features: Dict[str, float]) -> float:
        """Olasılık tahmini yap
        
        Args:
            features: Özellik dictionary'si
            
        Returns:
            Başarı olasılığı (0-1 arası)
        """
        z = self.bias
        
        for feature_name, feature_value in features.items():
            if feature_name in self.weights:
                z += self.weights[feature_name] * float(feature_value)
        
        return self._sigmoid(z)
    
    def update(self, features: Dict[str, float], true_label: int) -> None:
        """Online güncelleme yap
        
        Args:
            features: Özellik dictionary'si
            true_label: Gerçek etiket (0 veya 1)
        """
        # Tahmin yap
        predicted_proba = self.predict_proba(features)
        
        # Gradyan hesapla
        error = predicted_proba - true_label
        
        # Bias güncelle
        bias_gradient = error + self.l2_reg * self.bias
        self.bias -= self.lr * bias_gradient
        
        # Ağırlıkları güncelle
        for feature_name, feature_value in features.items():
            if feature_name in self.weights:
                weight_gradient = error * float(feature_value) + self.l2_reg * self.weights[feature_name]
                self.weights[feature_name] -= self.lr * weight_gradient
        
        self.samples_seen += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """İstatistikleri döndür"""
        return {
            'samples_seen': self.samples_seen,
            'bias': self.bias,
            'weights': self.weights.copy(),
            'learning_rate': self.lr,
            'l2_regularization': self.l2_reg
        }
    
    def reset(self) -> None:
        """Modeli sıfırla"""
        self.weights = {key: 0.0 for key in SCORING_WEIGHTS.keys()}
        self.bias = AI_INIT_BIAS
        self.samples_seen = 0


class AIPredictor:
    """AI tahmin sınıfı"""
    
    def __init__(self):
        self.model = OnlineLogisticRegression()
        self.enabled = AI_ENABLED
    
    def predict(self, features: Dict[str, float]) -> float:
        """Tahmin yap"""
        if not self.enabled:
            return 0.5  # Varsayılan olasılık
        
        return self.model.predict_proba(features)
    
    def learn_from_outcome(self, features: Dict[str, float], won: bool) -> None:
        """Sonuçtan öğren"""
        if not self.enabled:
            return
        
        label = 1 if won else 0
        self.model.update(features, label)
    
    def get_enhanced_probability(self, traditional_prob: float, features: Dict[str, float]) -> float:
        """Geleneksel olasılık ile AI tahminini birleştir"""
        if not self.enabled:
            return traditional_prob
        
        ai_prob = self.predict(features)
        
        # İki tahmini ortala (ağırlıklı ortalama da yapılabilir)
        return (traditional_prob + ai_prob) / 2.0
    
    def get_stats(self) -> Dict[str, Any]:
        """AI istatistikleri"""
        if not self.enabled:
            return {'enabled': False}
        
        stats = self.model.get_stats()
        stats['enabled'] = True
        return stats
    
    def reset(self) -> None:
        """AI'yı sıfırla"""
        if self.enabled:
            self.model.reset()
    
    def set_enabled(self, enabled: bool) -> None:
        """AI'yı aktif/pasif yap"""
        self.enabled = enabled


# Global AI instance
ai_predictor = AIPredictor()
