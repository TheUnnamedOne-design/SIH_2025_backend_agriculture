import torch
from torchvision import transforms
from PIL import Image
import timm
import os
import tempfile
from werkzeug.utils import secure_filename

class ImageClassificationService:
    def __init__(self, config):
        """Initialize image classification service"""
        # Device
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.checkpoint_path = config.get('IMAGE_MODEL_PATH', 'models/convnext_tiny_checkpoint.pth')
        
        # Model components
        self.model = None
        self.idx_to_class = None
        
        # Preprocessing (must match training)
        self.val_transforms = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],
                               std=[0.229, 0.224, 0.225])
        ])
        
        # Load model on initialization
        self.load_model()
    
    def load_model(self):
        """Load model checkpoint exactly as in your original code"""
        try:
            if not os.path.exists(self.checkpoint_path):
                print(f"⚠️ Model checkpoint not found: {self.checkpoint_path}")
                return False
            
            # Load checkpoint
            checkpoint = torch.load(self.checkpoint_path, map_location=self.device)
            
            # Reconstruct model (exactly as in your original code)
            num_classes = len(checkpoint["class_to_idx"])
            self.model = timm.create_model("convnext_tiny", pretrained=False, num_classes=num_classes)
            self.model.load_state_dict(checkpoint["model_state"])
            self.model.to(self.device)
            self.model.eval()
            
            # Reconstruct class mapping
            self.idx_to_class = {v: k for k, v in checkpoint["class_to_idx"].items()}
            
            print(f"✅ Image classification model loaded successfully")
            print(f"   Device: {self.device}")
            print(f"   Classes: {list(self.idx_to_class.values())}")
            print(f"   Num Classes: {num_classes}")
            return True
            
        except Exception as e:
            print(f"❌ Error loading image classification model: {e}")
            return False
    
    def predict_image(self, image_path):
        """
        Given an image path, returns the predicted class label with confidence.
        Based on your original predict_image function.
        """
        if self.model is None:
            return {"error": "Model not loaded", "confidence": 0.0}
        
        try:
            # Load image
            image = Image.open(image_path).convert("RGB")
            
            # Apply preprocessing
            image_tensor = self.val_transforms(image).unsqueeze(0)  # Add batch dimension
            image_tensor = image_tensor.to(self.device)
            
            # Forward pass
            with torch.no_grad():
                output = self.model(image_tensor)
                
                # Get probabilities for confidence scores
                probabilities = torch.softmax(output, dim=1)
                pred_idx = torch.argmax(output, dim=1).item()
                confidence = probabilities[0][pred_idx].item()
                pred_class = self.idx_to_class[pred_idx]
            
            return {
                "predicted_class": pred_class,
                "confidence": confidence,
                "all_predictions": {
                    self.idx_to_class[i]: probabilities[0][i].item() 
                    for i in range(len(self.idx_to_class))
                }
            }
            
        except Exception as e:
            print(f"Error in image prediction: {e}")
            return {"error": str(e), "confidence": 0.0}
    
    def predict_from_file_upload(self, file):
        """Predict from uploaded file"""
        if not file or not file.filename:
            return {"error": "No file uploaded", "confidence": 0.0}
        
        # Validate file type
        allowed_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}
        file_ext = os.path.splitext(file.filename.lower())[1]
        if file_ext not in allowed_extensions:
            return {"error": f"Unsupported file type: {file_ext}", "confidence": 0.0}
        
        try:
            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as temp_file:
                file.save(temp_file.name)
                temp_path = temp_file.name
            
            # Make prediction
            result = self.predict_image(temp_path)
            
            # Clean up temp file
            os.unlink(temp_path)
            
            return result
            
        except Exception as e:
            print(f"Error processing uploaded file: {e}")
            return {"error": str(e), "confidence": 0.0}
