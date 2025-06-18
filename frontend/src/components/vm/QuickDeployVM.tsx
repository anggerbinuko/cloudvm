import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from '../common/Button';
import credentialsService from '../../services/credentialsService';
import terraformService from '../../services/terraformService';
import { VMDeploymentRequest } from '../../services/terraformService';
import { toast } from 'react-hot-toast';

// Enum untuk status deployment
enum DeploymentStatus {
  IDLE = 'idle',
  CREATING = 'creating',
  PROVISIONING = 'provisioning',
  CONFIGURING = 'configuring',
  STARTING = 'starting',
  RUNNING = 'running',
  FAILED = 'failed'
}

interface FormData {
  name: string;
  provider: string;
  region: string;
  credential_id: number | null;
  instance_type: string;
  preset: string;
  resources: {
    cpu: number;
    ram: number;
    storage: number;
  };
  network: {
    public_ip: boolean;
  };
}

interface Credential {
  id: number;
  name: string;
  type: string;
}

interface Region {
  id: string;
  name: string;
}

interface Regions {
  gcp: Region[];
  aws: Region[];
}

interface VMPreset {
  id: string;
  name: string;
  description: string;
  icon: string;
  specs: {
    cpu: number;
    ram: number;
    storage: number;
    instance_type: string;
  };
  details: string[];
  price: string;
}

const QuickDeployVM: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'gcp' | 'aws'>('gcp');
  const [selectedPreset, setSelectedPreset] = useState<string>('gcp-low-cost');
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCredential, setSelectedCredential] = useState<number | null>(null);
  const [isDeploying, setIsDeploying] = useState<boolean>(false);
  const [deploymentStatus, setDeploymentStatus] = useState<DeploymentStatus>(DeploymentStatus.IDLE);
  const [deploymentProgress, setDeploymentProgress] = useState<number>(0);
  const [deploymentSteps, setDeploymentSteps] = useState<{step: string, completed: boolean}[]>([
    { step: 'Menyiapkan infrastruktur', completed: false },
    { step: 'Membuat VM', completed: false },
    { step: 'Mengkonfigurasi jaringan', completed: false },
    { step: 'Menginisialisasi sistem', completed: false },
    { step: 'Memulai VM', completed: false }
  ]);
  const [isPolling, setIsPolling] = useState<boolean>(false);
  const [vmId, setVmId] = useState<string | null>(null);
  
  const [formData, setFormData] = useState<FormData>({
    name: '',
    provider: 'gcp',
    region: '',
    credential_id: null,
    instance_type: 'e2-micro',
    preset: 'gcp-low-cost',
    resources: {
      cpu: 2,
      ram: 1,
      storage: 10
    },
    network: {
      public_ip: true
    }
  });

  const regions: Regions = {
    gcp: [
      { id: 'us-central1', name: 'US Central (Iowa)' },
      { id: 'us-east1', name: 'US East (South Carolina)' },
      { id: 'us-west1', name: 'US West (Oregon)' },
      { id: 'asia-east1', name: 'Asia East (Taiwan)' },
      { id: 'asia-southeast1', name: 'Asia Southeast (Singapore)' },
      { id: 'europe-west1', name: 'Europe West (Belgium)' }
    ],
    aws: [
      { id: 'us-east-1', name: 'US East (N. Virginia)' },
      { id: 'us-east-2', name: 'US East (Ohio)' },
      { id: 'us-west-1', name: 'US West (N. California)' },
      { id: 'us-west-2', name: 'US West (Oregon)' },
      { id: 'ap-southeast-1', name: 'Asia Pacific (Singapore)' },
      { id: 'ap-southeast-2', name: 'Asia Pacific (Sydney)' },
      { id: 'eu-west-1', name: 'Europe (Ireland)' }
    ]
  };

  // GCP VM Presets
  const gcpPresets: VMPreset[] = [
    {
      id: 'gcp-low-cost',
      name: 'Low cost',
      description: 'Explore Google Cloud dengan VM kecil, hemat biaya yang ideal untuk beban kerja non-produksi',
      icon: 'M9 2a1 1 0 000 2h2a1 1 0 100-2H9z M4 5a2 2 0 012-2 1 1 0 010 2H4zm9 0a1 1 0 00-1-1h-2a1 1 0 000 2h2a1 1 0 001-1zm-5 4a1 1 0 110-2 1 1 0 010 2zm3 1a1 1 0 100-2 1 1 0 000 2zm-7 0a1 1 0 100-2 1 1 0 000 2zm7 4a1 1 0 110-2 1 1 0 010 2zm-7 0a1 1 0 110-2 1 1 0 010 2zm10-4a1 1 0 110-2 1 1 0 010 2zm-7 4a1 1 0 110-2 1 1 0 010 2z M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4',
      specs: {
        cpu: 2,
        ram: 1,
        storage: 10,
        instance_type: 'e2-micro'
      },
      details: [
        '2 vCPUs + 1 GB memory',
        'Intel atau AMD',
        'Ideal untuk pengembangan dan pengujian'
      ],
      price: 'Rp50.000/bulan'
    },
    {
      id: 'gcp-web-server',
      name: 'Web server',
      description: 'VM hemat biaya untuk komputasi sehari-hari, seperti hosting situs web dasar',
      icon: 'M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z',
      specs: {
        cpu: 2,
        ram: 4,
        storage: 20,
        instance_type: 'e2-medium'
      },
      details: [
        '2 vCPUs + 4 GB memory',
        'Intel atau AMD',
        'Cocok untuk web server dan aplikasi kecil'
      ],
      price: 'Rp135.000/bulan'
    },
    {
      id: 'gcp-app-server',
      name: 'Application server',
      description: 'VM harga dan performa seimbang untuk aplikasi, seperti Java atau CRMs',
      icon: 'M5 3a2 2 0 00-2 2v3a2 2 0 002 2h10a2 2 0 002-2V5a2 2 0 00-2-2H5zM5 11a2 2 0 00-2 2v3a2 2 0 002 2h10a2 2 0 002-2v-3a2 2 0 00-2-2H5z',
      specs: {
        cpu: 2,
        ram: 8,
        storage: 40,
        instance_type: 'e2-standard-2'
      },
      details: [
        '2 vCPUs + 8 GB memory',
        'Intel',
        'Ideal untuk aplikasi bisnis dan database'
      ],
      price: 'Rp275.000/bulan'
    }
  ];

  // AWS VM Presets
  const awsPresets: VMPreset[] = [
    {
      id: 'aws-low-cost',
      name: 'Low cost',
      description: 'Ideal untuk menjalankan aplikasi mikro dengan biaya rendah',
      icon: 'M9 2a1 1 0 000 2h2a1 1 0 100-2H9z M4 5a2 2 0 012-2 1 1 0 010 2H4zm9 0a1 1 0 00-1-1h-2a1 1 0 000 2h2a1 1 0 001-1zm-5 4a1 1 0 110-2 1 1 0 010 2zm3 1a1 1 0 100-2 1 1 0 000 2zm-7 0a1 1 0 100-2 1 1 0 000 2zm7 4a1 1 0 110-2 1 1 0 010 2zm-7 0a1 1 0 110-2 1 1 0 010 2zm10-4a1 1 0 110-2 1 1 0 010 2zm-7 4a1 1 0 110-2 1 1 0 010 2z M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4',
      specs: {
        cpu: 1,
        ram: 1,
        storage: 8,
        instance_type: 't2.micro'
      },
      details: [
        '1 vCPU + 1 GB memory',
        'Cocok untuk aplikasi mikro',
        'Termasuk dalam tier gratis AWS'
      ],
      price: 'Rp45.000/bulan'
    },
    {
      id: 'aws-web-server',
      name: 'Web server',
      description: 'Pilihan seimbang untuk hosting website dan aplikasi web',
      icon: 'M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z',
      specs: {
        cpu: 2,
        ram: 4,
        storage: 20,
        instance_type: 't2.medium'
      },
      details: [
        '2 vCPUs + 4 GB memory',
        'Cocok untuk situs web dan aplikasi',
        'Performa berimbang'
      ],
      price: 'Rp150.000/bulan'
    },
    {
      id: 'aws-app-server',
      name: 'Application server',
      description: 'Optimal untuk aplikasi bisnis dan database',
      icon: 'M5 3a2 2 0 00-2 2v3a2 2 0 002 2h10a2 2 0 002-2V5a2 2 0 00-2-2H5zM5 11a2 2 0 00-2 2v3a2 2 0 002 2h10a2 2 0 002-2v-3a2 2 0 00-2-2H5z',
      specs: {
        cpu: 2,
        ram: 8,
        storage: 40,
        instance_type: 'm5.large'
      },
      details: [
        '2 vCPUs + 8 GB memory',
        'Komputasi tujuan umum',
        'Ideal untuk aplikasi bisnis'
      ],
      price: 'Rp290.000/bulan'
    }
  ];

  useEffect(() => {
    const fetchCredentials = async () => {
      try {
        setIsLoading(true);
        const data = await credentialsService.getAll();
        setCredentials(data);
        setError(null);
      } catch (err: any) {
        setError('Gagal memuat kredensial: ' + (err.message || 'Terjadi kesalahan'));
        console.error('Error fetching credentials:', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchCredentials();
  }, []);

  // Filter kredensial berdasarkan provider yang dipilih
  const filteredCredentials = credentials.filter(cred => 
    (formData.provider === 'aws' && cred.type === 'aws') || 
    (formData.provider === 'gcp' && cred.type === 'gcp')
  );

  const handleTabChange = (tab: 'gcp' | 'aws') => {
    setActiveTab(tab);
      setFormData({
        ...formData,
      provider: tab,
      region: '',
      preset: tab === 'gcp' ? 'gcp-low-cost' : 'aws-low-cost',
      instance_type: tab === 'gcp' ? 'e2-micro' : 't2.micro',
      resources: {
        cpu: tab === 'gcp' ? 2 : 1,
        ram: 1,
        storage: tab === 'gcp' ? 10 : 8
      }
    });
    setSelectedPreset(tab === 'gcp' ? 'gcp-low-cost' : 'aws-low-cost');
    setSelectedCredential(null);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData({
      ...formData,
      [name]: value
    });
  };

  const handleRegionChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setFormData({
      ...formData,
      region: e.target.value
    });
  };

  const handleCredentialSelect = (id: number) => {
    setSelectedCredential(id);
  };

  const handlePresetSelect = (presetId: string) => {
    setSelectedPreset(presetId);
    
    const presets = formData.provider === 'gcp' ? gcpPresets : awsPresets;
    const selectedPresetData = presets.find(p => p.id === presetId);
    
    if (selectedPresetData) {
      setFormData({
        ...formData,
        preset: presetId.replace(formData.provider + '-', ''),  // Konversi id ke nama preset yang dikenali backend
        instance_type: selectedPresetData.specs.instance_type,
        resources: {
          cpu: selectedPresetData.specs.cpu,
          ram: selectedPresetData.specs.ram,
          storage: selectedPresetData.specs.storage
        }
      });
    }
  };

  // Function untuk update progress deployment
  const updateDeploymentProgress = (status: string) => {
    let newProgress = 0;
    const updatedSteps = [...deploymentSteps];
    
    // Normalize status ke uppercase untuk konsistensi
    const normalizedStatus = status.toUpperCase();
    
    if (normalizedStatus.includes('CREATING')) {
      setDeploymentStatus(DeploymentStatus.CREATING);
      newProgress = 20;
      updatedSteps[0].completed = true;
    } else if (normalizedStatus.includes('PROVISIONING')) {
      setDeploymentStatus(DeploymentStatus.PROVISIONING);
      newProgress = 40;
      updatedSteps[0].completed = true;
      updatedSteps[1].completed = true;
    } else if (normalizedStatus.includes('CONFIGURING')) {
      setDeploymentStatus(DeploymentStatus.CONFIGURING);
      newProgress = 60;
      updatedSteps[0].completed = true;
      updatedSteps[1].completed = true;
      updatedSteps[2].completed = true;
    } else if (normalizedStatus.includes('STAGING')) {
      setDeploymentStatus(DeploymentStatus.STARTING);
      newProgress = 80;
      updatedSteps[0].completed = true;
      updatedSteps[1].completed = true;
      updatedSteps[2].completed = true;
      updatedSteps[3].completed = true;
    } else if (normalizedStatus === 'RUNNING' || normalizedStatus.includes('ACTIVE') || normalizedStatus.includes('READY')) {
      setDeploymentStatus(DeploymentStatus.RUNNING);
      newProgress = 100;
      updatedSteps.forEach(step => step.completed = true);
      
      // Show success toast only once
      if (deploymentProgress !== 100) {
        toast.success('VM berhasil dibuat dan sedang berjalan!', {
          duration: 5000,
          icon: '🎉'
        });
      }
    } else if (normalizedStatus.includes('FAILED') || normalizedStatus.includes('ERROR')) {
      setDeploymentStatus(DeploymentStatus.FAILED);
      
      // Show error toast
      toast.error('Gagal membuat VM. Silakan periksa log untuk detail.', {
        duration: 5000
      });
    } else {
      // Default case for other statuses
      console.log('Status VM:', normalizedStatus);
      // Don't show any toast for intermediate states
    }
    
    setDeploymentProgress(newProgress);
    setDeploymentSteps(updatedSteps);
  };

  // Function to deploy VM
  const handleDeploy = async () => {
    if (!formData.name) {
      setError('Mohon isi nama VM');
      toast.error('Mohon isi nama VM');
      return;
    }
    
    if (!formData.region) {
      setError('Pilih region untuk VM');
      toast.error('Pilih region untuk VM');
      return;
    }
    
    if (!selectedCredential) {
      setError('Pilih kredensial terlebih dahulu');
      toast.error('Pilih kredensial terlebih dahulu');
      return;
    }

    try {
      setIsDeploying(true);
      setError(null);
      setIsPolling(true);
      setDeploymentStatus(DeploymentStatus.CREATING);
      setDeploymentProgress(10);
      
      // Tampilkan toast untuk memulai deployment
      toast.loading('Memulai deployment VM...', {
        id: 'deployment-start'
      });
      
      // Reset deployment steps
      const initialSteps = [
        { step: 'Menyiapkan infrastruktur', completed: false },
        { step: 'Membuat VM', completed: false },
        { step: 'Mengkonfigurasi jaringan', completed: false },
        { step: 'Menginisialisasi sistem', completed: false },
        { step: 'Memulai VM', completed: false }
      ];
      setDeploymentSteps(initialSteps);
      
      // Extract preset from ID (remove provider prefix)
      const presetName = selectedPreset.replace(formData.provider + '-', '');
      
      // Format data sesuai dengan model backend
      const deploymentData: VMDeploymentRequest = {
        name: formData.name,
        provider: formData.provider.toLowerCase(),
        region: formData.region,
        credential_id: selectedCredential,
        instance_type: formData.instance_type,
        preset: presetName,
        resources: {
          cpu: formData.resources.cpu,
          memory: formData.resources.ram,
          storage: formData.resources.storage
        },
        network: {
          public_ip: formData.network.public_ip
        }
      };
      
      // Tambahkan zone untuk GCP
      if (formData.provider.toLowerCase() === 'gcp') {
        deploymentData.zone = `${formData.region}-a`;
      }
      
      console.log('[handleDeploy] Deployment data to be sent:', deploymentData);

      try {
        // Update step 1
        setDeploymentSteps(prev => {
          const updated = [...prev];
          updated[0].completed = true;
          return updated;
        });
        setDeploymentProgress(20);
        
        // Dismiss loading toast
        toast.dismiss('deployment-start');
        
        // Coba dengan terraformService standar
        const response = await terraformService.deployVM(deploymentData);
        console.log('[handleDeploy] Deployment response:', response);
        
        // Save VM ID untuk polling
        setVmId(response.id);
        
        // Update step 2
        setDeploymentSteps(prev => {
          const updated = [...prev];
          updated[1].completed = true;
          return updated;
        });
        setDeploymentProgress(40);
        
        // Mulai polling status
        const finalStatus = await terraformService.pollVMStatus(
          response.id,
          (status) => {
            console.log('[handleDeploy] Status update:', status);
            updateDeploymentProgress(status);
          }
        );
        
        // Cek status VM dengan lebih fleksibel
        if (finalStatus.status.toUpperCase().includes('RUNNING') || 
            finalStatus.status.toUpperCase() === 'ACTIVE' ||
            finalStatus.status.toUpperCase() === 'READY') {
          // Update toast dengan sukses
          toast.success(`VM "${formData.name}" berhasil dibuat dan sedang berjalan! Provider: ${formData.provider.toUpperCase()}, Region: ${formData.region}`, {
            duration: 5000,
            icon: '🚀'
          });
          
          // Navigasi ke dashboard setelah 2 detik
          setTimeout(() => {
            navigate('/dashboard');
          }, 3000);
        } else if (finalStatus.status.toUpperCase().includes('FAILED') || 
                   finalStatus.status.toUpperCase().includes('ERROR')) {
          // Handle failed status
          toast.error(`VM gagal dibuat. Status: ${finalStatus.status}. Silakan cek di dashboard.`);
          setTimeout(() => {
            navigate('/dashboard');
          }, 3000);
        } else {
          // Handle other statuses as success karena VM mungkin masih dalam proses akhir
          toast.success(`VM "${formData.name}" berhasil dibuat! Status: ${finalStatus.status}`, {
            duration: 5000,
            icon: '🚀'
          });
          setTimeout(() => {
            navigate('/dashboard');
          }, 3000);
        }
      } catch (error: any) {
        console.error('[handleDeploy] Error deploying VM:', error);
        setError(error.message || 'Terjadi kesalahan saat membuat VM');
        setDeploymentStatus(DeploymentStatus.FAILED);
        
        // Update toast dengan error
        toast.error(`Error: ${error.message || 'Terjadi kesalahan saat membuat VM'}`, {
          duration: 5000
        });
        
        // Bahkan jika ada error, tetap arahkan ke dashboard untuk mengecek
        toast.error('Silakan cek status VM di dashboard');
        setTimeout(() => {
          navigate('/dashboard');
        }, 3000);
      }
      
    } catch (error: any) {
      console.error('[handleDeploy] Error in deploy process:', error);
      setError(error.message || 'Terjadi kesalahan saat memproses permintaan');
      setDeploymentStatus(DeploymentStatus.FAILED);
      
      toast.error(`Error: ${error.message || 'Terjadi kesalahan saat memproses permintaan'}`);
    } finally {
      setIsDeploying(false);
      setIsPolling(false);
    }
  };

  // Function untuk cancel deployment
  const handleCancelDeployment = async () => {
    if (vmId) {
      toast.loading('Membatalkan deployment...', { id: 'cancel-deployment' });
      
      try {
        // Di sini Anda bisa menambahkan logic untuk cancel deployment dengan memanggil API
        // await terraformService.cancelDeployment(vmId);
        
        toast.success('Deployment dibatalkan', { id: 'cancel-deployment' });
        setIsPolling(false);
        setIsDeploying(false);
        setDeploymentStatus(DeploymentStatus.IDLE);
      } catch (error: any) {
        toast.error(`Gagal membatalkan: ${error.message}`, { id: 'cancel-deployment' });
      }
    }
  };

  // Function untuk mendapatkan pesan status yang user-friendly
  const getStatusMessage = () => {
    switch(deploymentStatus) {
      case DeploymentStatus.CREATING:
        return 'Membuat VM...';
      case DeploymentStatus.PROVISIONING:
        return 'Menyediakan resource...';
      case DeploymentStatus.CONFIGURING:
        return 'Mengkonfigurasi VM...';
      case DeploymentStatus.STARTING:
        return 'Memulai VM...';
      case DeploymentStatus.RUNNING:
        return 'VM berhasil dibuat dan sedang berjalan!';
      case DeploymentStatus.FAILED:
        return 'Gagal membuat VM';
      default:
        return 'Memproses...';
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-2">Quick VM Deployment</h1>
      <p className="text-gray-600 mb-6">Pilih preset VM yang sesuai dengan kebutuhan Anda</p>

      {/* Provider Tabs */}
      <div className="flex border-b mb-6">
        <button
          className={`py-3 px-6 font-medium ${
            activeTab === 'gcp'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
          onClick={() => handleTabChange('gcp')}
          disabled={isDeploying}
        >
          Google Cloud
        </button>
        <button
          className={`py-3 px-6 font-medium ${
            activeTab === 'aws'
              ? 'text-blue-600 border-b-2 border-blue-600'
              : 'text-gray-500 hover:text-gray-700'
          }`}
          onClick={() => handleTabChange('aws')}
          disabled={isDeploying}
        >
          AWS
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4">Pilih VM Preset</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            {(activeTab === 'gcp' ? gcpPresets : awsPresets).map((preset) => (
              <div
                key={preset.id}
                className={`border rounded-lg p-4 cursor-pointer transition-all ${
                  selectedPreset === preset.id
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-blue-300 hover:bg-blue-50/50'
                } ${isDeploying ? 'opacity-70 pointer-events-none' : ''}`}
                onClick={() => !isDeploying && handlePresetSelect(preset.id)}
              >
                <div className="flex items-start mb-2">
                  <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center mr-3">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      className="h-6 w-6 text-gray-600"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1.5}
                        d={preset.icon}
                      />
                    </svg>
                  </div>
    <div>
                    <h3 className="font-medium text-gray-900">{preset.name}</h3>
                    <p className="text-sm text-gray-500">{preset.description}</p>
                  </div>
                </div>
                
                <div className="border-t border-dashed pt-3 mt-3">
                  <ul className="space-y-1 text-sm">
                    {preset.details.map((detail, idx) => (
                      <li key={idx} className="text-gray-600">
                        {detail}
                      </li>
                    ))}
                  </ul>
                  <div className="font-medium text-gray-900 mt-2">
                    {preset.price}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-bold mb-4">Konfigurasi VM</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
        <div>
              <label htmlFor="vm-name" className="block text-sm font-medium text-gray-700 mb-1">
                Nama VM
          </label>
          <input
            type="text"
                id="vm-name"
            name="name"
            value={formData.name}
            onChange={handleInputChange}
            className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                placeholder="Masukkan nama VM"
            required
                disabled={isDeploying}
          />
        </div>

        <div>
          <label htmlFor="region" className="block text-sm font-medium text-gray-700 mb-1">
            Region
          </label>
          <select
            id="region"
            name="region"
            value={formData.region}
                onChange={handleRegionChange}
            className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            required
                disabled={isDeploying}
          >
                <option value="" disabled>Pilih region</option>
                {regions[activeTab].map((region: Region) => (
              <option key={region.id} value={region.id}>
                {region.name}
              </option>
            ))}
          </select>
            </div>
        </div>

          <div className="mb-6">
            <label htmlFor="credentials" className="block text-sm font-medium text-gray-700 mb-1">
              Kredensial
          </label>
            <div id="credentials">
          {isLoading ? (
            <div className="flex items-center justify-center p-4 border border-gray-300 rounded-md">
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-500 mr-2"></div>
                <span>Loading kredensial...</span>
            </div>
          ) : filteredCredentials.length === 0 ? (
            <div className="p-4 border border-yellow-300 bg-yellow-50 rounded-md">
                <p className="text-yellow-700">Tidak ditemukan kredensial untuk {activeTab === 'gcp' ? 'Google Cloud' : 'AWS'}.</p>
              <button
                type="button"
                className="mt-2 text-blue-600 hover:text-blue-800"
                onClick={() => navigate('/credentials')}
                  disabled={isDeploying}
              >
                  Kelola Kredensial
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {filteredCredentials.map(credential => (
                <div
                  key={credential.id}
                  className={`p-3 border rounded-md cursor-pointer ${
                    selectedCredential === credential.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-300 hover:bg-gray-50'
                    } ${isDeploying ? 'opacity-70 pointer-events-none' : ''}`}
                    onClick={() => !isDeploying && handleCredentialSelect(credential.id)}
                >
                  <div className="font-medium">{credential.name}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

          <div className="bg-blue-50 p-4 rounded-md mb-6">
            <h3 className="text-sm font-medium text-blue-800 mb-1">Spesifikasi VM</h3>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <span className="text-gray-500">CPU:</span> {formData.resources.cpu} vCPUs
    </div>
    <div>
                <span className="text-gray-500">RAM:</span> {formData.resources.ram} GB
              </div>
        <div>
                <span className="text-gray-500">Storage:</span> {formData.resources.storage} GB
          </div>
        </div>
          </div>

          {error && (
            <div className="p-4 border border-red-300 bg-red-50 rounded-md mb-4">
              <p className="text-red-700">{error}</p>
        </div>
          )}

          <div className="flex justify-end">
            <Button
              variant="outline"
              onClick={() => navigate('/create-vm')}
              className="mr-4"
              disabled={isDeploying}
            >
              Kembali
            </Button>
            <Button
              variant="primary"
              onClick={handleDeploy}
              disabled={isDeploying || !selectedCredential || !formData.name || !formData.region}
            >
              {isDeploying ? 'Membuat VM...' : 'Deploy VM'}
            </Button>
          </div>
        </div>
      </div>

      {isPolling && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white p-6 rounded-lg shadow-lg max-w-md w-full">
            <div className="mb-4">
              <h3 className="text-lg font-medium mb-2">{getStatusMessage()}</h3>
              
              <div className="w-full bg-gray-200 rounded-full h-2.5 mb-4">
                <div className="bg-blue-600 h-2.5 rounded-full transition-all duration-500 ease-in-out" 
                     style={{ width: `${deploymentProgress}%` }}>
          </div>
        </div>

              <ul className="space-y-3">
                {deploymentSteps.map((step, idx) => (
                  <li key={idx} className="flex items-center">
                    {step.completed ? (
                      <svg className="w-5 h-5 text-green-500 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
                  </svg>
                    ) : idx === deploymentSteps.findIndex(s => !s.completed) ? (
                      <div className="w-5 h-5 border-t-2 border-blue-500 rounded-full animate-spin mr-2"></div>
                    ) : (
                      <div className="w-5 h-5 rounded-full border border-gray-300 mr-2"></div>
                    )}
                    <span className={`${step.completed ? 'text-gray-700' : idx === deploymentSteps.findIndex(s => !s.completed) ? 'text-blue-600 font-medium' : 'text-gray-400'}`}>
                      {step.step}
                    </span>
                  </li>
                ))}
              </ul>
      </div>

            <div className="flex justify-end gap-2">
              {deploymentStatus !== DeploymentStatus.RUNNING && deploymentStatus !== DeploymentStatus.FAILED && (
        <Button
          variant="outline"
                  onClick={handleCancelDeployment}
        >
                  Batalkan
        </Button>
              )}
              {(deploymentStatus === DeploymentStatus.RUNNING || deploymentStatus === DeploymentStatus.FAILED) && (
        <Button
          variant="primary"
                  onClick={() => navigate('/dashboard')}
        >
                  Ke Dashboard
        </Button>
              )}
            </div>
          </div>
      </div>
      )}
    </div>
  );
};

export default QuickDeployVM; 
