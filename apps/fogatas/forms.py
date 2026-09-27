from django import forms
from apps.canciones.models import Cancion
from .models import Fogata, FogataCancion


class FogataForm(forms.ModelForm):
    class Meta:
        model = Fogata
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Ej: Acústicos fogata sábado',
                'required': True,
                'autocomplete': 'off',
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'placeholder': 'Breve descripción o notas generales...',
            }),
        }


class AgregarCancionForm(forms.Form):
    cancion = forms.ModelChoiceField(
        queryset=Cancion.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Seleccionar Canción'
    )
    nota_sesion = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Nota opcional (ej: Tono D, solo estrofas)',
        }),
        label='Nota para la sesión'
    )

    def __init__(self, *args, **kwargs):
        fogata = kwargs.pop('fogata', None)
        super().__init__(*args, **kwargs)
        if fogata and fogata.propietario:
            # Excluir canciones que ya estén en esta fogata y restringir al propietario
            canciones_existentes = fogata.canciones_asociadas.values_list('cancion_id', flat=True)
            self.fields['cancion'].queryset = Cancion.objects.filter(
                propietario=fogata.propietario
            ).exclude(id__in=canciones_existentes)
        else:
            self.fields['cancion'].queryset = Cancion.objects.none()


class CrearSesionCompartidaForm(forms.Form):
    DURACION_OPCIONES = [
        (2, '2 horas'),
        (4, '4 horas'),
        (8, '8 horas (Recomendado)'),
        (12, '12 horas'),
        (24, '24 horas (1 día)'),
        (48, '48 horas (2 días)'),
    ]
    duracion_horas = forms.ChoiceField(
        choices=DURACION_OPCIONES,
        initial=8,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Duración del enlace'
    )
