import React from 'react';
import { HistoryEvent } from '../../types/history';

interface Props {
  event: HistoryEvent | null;
  onClose: () => void;
}

const HistoryDetailModal: React.FC<Props> = ({ event, onClose }) => {
  if (!event) return null;

  return (
    <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full flex items-center justify-center">
      <div className="relative mx-auto p-5 border w-full max-w-3xl shadow-lg rounded-md bg-white">
        <div className="flex justify-between items-center border-b pb-3">
          <h3 className="text-2xl font-bold">Detail Aktivitas</h3>
          <button onClick={onClose} className="text-black">
            &times;
          </button>
        </div>
        <div className="mt-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p className="font-semibold">ID Event:</p>
              <p>{event.id}</p>
            </div>
            <div>
              <p className="font-semibold">Waktu:</p>
              <p>{new Date(event.timestamp).toLocaleString()}</p>
            </div>
            <div>
              <p className="font-semibold">Tipe Aktivitas:</p>
              <p>{event.event_type}</p>
            </div>
            <div>
              <p className="font-semibold">Status:</p>
              <p>{event.status}</p>
            </div>
            <div>
              <p className="font-semibold">User ID:</p>
              <p>{event.user_id}</p>
            </div>
            {event.vm_id && (
              <div>
                <p className="font-semibold">VM ID:</p>
                <p>{event.vm_id}</p>
              </div>
            )}
            {event.credential_id && (
              <div>
                <p className="font-semibold">Credential ID:</p>
                <p>{event.credential_id}</p>
              </div>
            )}
            {event.duration && (
              <div>
                <p className="font-semibold">Durasi:</p>
                <p>{event.duration.toFixed(2)} detik</p>
              </div>
            )}
          </div>
          <div className="mt-4">
            <p className="font-semibold">Parameter:</p>
            <pre className="bg-gray-100 p-2 rounded mt-1 text-sm overflow-auto">
              {JSON.stringify(event.parameters, null, 2)}
            </pre>
          </div>
          {event.result && (
            <div className="mt-4">
              <p className="font-semibold">Hasil:</p>
              <pre className="bg-gray-100 p-2 rounded mt-1 text-sm overflow-auto">
                {JSON.stringify(event.result, null, 2)}
              </pre>
            </div>
          )}
          {event.error_message && (
            <div className="mt-4">
              <p className="font-semibold">Pesan Error:</p>
              <pre className="bg-red-100 p-2 rounded mt-1 text-sm overflow-auto">
                {event.error_message}
              </pre>
            </div>
          )}
        </div>
        <div className="flex justify-end pt-2 border-t mt-5">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-500 text-white text-base font-medium rounded-md shadow-sm hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500"
          >
            Tutup
          </button>
        </div>
      </div>
    </div>
  );
};

export default HistoryDetailModal;