from django import forms
from .models import Cancion


class CancionForm(forms.ModelForm):
    contenido = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-textarea font-mono',
            'rows': 20,
            'placeholder': 'Pega aquí la letra con acordes.\n\nEjemplo:\n       Bm           G          D           A\nElla durmió al calor de las masas...',
            'required': True,
            'spellcheck': 'false',
            'autocapitalize': 'off',
            'autocorrect': 'off',
            'autocomplete': 'off',
            'wrap': 'off',  # Para evitar que el navegador auto-rompa las líneas al editar
        }),
        strip=False,
        required=True,
        label='Contenido (Letra + Acordes)',
        help_text='Texto íntegro tal como fue copiado/escrito. Se preservan espacios y saltos de línea.'
    )

    capo = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=12,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-input form-input-short',
            'min': '0',
            'max': '12',
            'placeholder': '0',
        }),
        label='Capo / Cejillo',
        help_text='0 si no usa'
    )

    def clean_capo(self):
        val = self.cleaned_data.get('capo')
        if val is None or val == '':
            return 0
        return val

    class Meta:
        model = Cancion
        fields = [
            'titulo',
            'artista',
            'tonalidad',
            'capo',
            'afinacion',
            'contenido',
            'notas_personales',
        ]
        widgets = {
            'titulo': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ej: De música ligera',
                'required': True,
                'autocomplete': 'off',
            }),
            'artista': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ej: Soda Stereo',
                'autocomplete': 'off',
            }),
            'tonalidad': forms.TextInput(attrs={
                'class': 'form-input form-input-short',
                'placeholder': 'Ej: Bm',
            }),
            'capo': forms.NumberInput(attrs={
                'class': 'form-input form-input-short',
                'min': '0',
                'max': '12',
            }),
            'afinacion': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ej: Estándar (E A D G B E)',
            }),
            'contenido': forms.Textarea(attrs={
                'class': 'form-textarea font-mono',
                'rows': 20,
                'placeholder': 'Pega aquí la letra con acordes.\n\nEjemplo:\n       Bm           G          D           A\nElla durmió al calor de las masas...',
                'required': True,
                'spellcheck': 'false',
                'autocapitalize': 'off',
                'autocorrect': 'off',
                'autocomplete': 'off',
                'wrap': 'off',  # Para evitar que el navegador auto-rompa las líneas al editar
            }),
            'notas_personales': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Notas de interpretación, rasgueo, intro...',
            }),
        }
