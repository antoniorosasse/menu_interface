from django.db import models

# Create your models here.
class EmpresaCompleta(models.Model):
    cnpj_completo = models.CharField(max_length=14, primary_key=True)
    razao_social = models.CharField(max_length=255)
    # ... outros campos ...
    
    class Meta:
        managed = False           # já tem, provavelmente
        db_table = 'vw_empresa_completa'
        default_permissions = ()  # se for read-only
    
    @classmethod
    def buscar_otimizado(cls, termo, limit=20):
        """Busca otimizada com apenas os campos necessários"""
        return cls.objects.filter(
            razao_social__icontains=termo
        ).values(
            'cnpj_completo',
            'razao_social',
            'nm_fantasia',
            'uf',
            'situacao_descricao',
            'total_socios'
        ).order_by('razao_social')[:limit]
