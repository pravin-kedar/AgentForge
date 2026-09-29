import { useAuth } from "../hooks/useAuth";

export function Profile() {
  const { user } = useAuth();

  return (
    <div className="mx-auto max-w-md px-6 py-12">
      <h1 className="mb-6 text-xl font-semibold text-gray-800">Profile</h1>
      <dl className="space-y-4 rounded-lg border border-gray-200 bg-white p-6">
        <div>
          <dt className="text-xs uppercase text-gray-400">Full name</dt>
          <dd className="text-sm text-gray-800">{user?.full_name || "-"}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-gray-400">Email</dt>
          <dd className="text-sm text-gray-800">{user?.email}</dd>
        </div>
        <div>
          <dt className="text-xs uppercase text-gray-400">User ID</dt>
          <dd className="text-sm text-gray-800">{user?.id}</dd>
        </div>
      </dl>
    </div>
  );
}
