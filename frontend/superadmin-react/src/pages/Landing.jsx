import { Shield, BarChart3, Users, ArrowRight } from "lucide-react";
import { useNavigate } from "react-router-dom";

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-white text-gray-900">

      {/* NAVBAR */}
      <header className="flex justify-between items-center px-8 py-6 border-b">
        <div className="text-xl font-bold">SecureVU</div>

        <div className="flex items-center gap-6">
          <button
            className="text-sm font-medium"
            onClick={() => navigate("/auth")}
          >
            Login
          </button>

          <button
            className="bg-black text-white px-4 py-2 rounded-lg text-sm"
            onClick={() => navigate("/auth")}
          >
            Dashboard
          </button>
        </div>
      </header>

      {/* HERO */}
      <section className="text-center py-24 px-6">
        <h1 className="text-4xl md:text-5xl font-bold mb-6">
          Smarter Client & Subscription Management
        </h1>

        <p className="text-gray-600 max-w-2xl mx-auto mb-8">
          SecureVU helps you manage clients, billing, subscriptions and analytics
          in one unified dashboard.
        </p>

        <button
          className="bg-black text-white px-6 py-3 rounded-lg flex items-center gap-2 mx-auto"
          onClick={() => navigate("/auth")}
        >
          Get Started
          <ArrowRight size={18} />
        </button>
      </section>

      {/* FEATURES */}
      <section className="grid md:grid-cols-3 gap-10 px-8 py-20 bg-gray-50">

        <div className="text-center">
          <Shield className="mx-auto mb-4" size={32} />
          <h3 className="font-semibold text-lg mb-2">Secure & Reliable</h3>
          <p className="text-gray-600 text-sm">
            Enterprise-level security and data protection.
          </p>
        </div>

        <div className="text-center">
          <BarChart3 className="mx-auto mb-4" size={32} />
          <h3 className="font-semibold text-lg mb-2">Billing Insights</h3>
          <p className="text-gray-600 text-sm">
            Monitor revenue, renewals and performance in real time.
          </p>
        </div>

        <div className="text-center">
          <Users className="mx-auto mb-4" size={32} />
          <h3 className="font-semibold text-lg mb-2">Client Control</h3>
          <p className="text-gray-600 text-sm">
            Manage subscriptions and client accounts effortlessly.
          </p>
        </div>

      </section>

      {/* CTA */}
      <section className="text-center py-20">
        <h2 className="text-3xl font-bold mb-6">
          Ready to simplify your operations?
        </h2>

        <button
          className="bg-black text-white px-6 py-3 rounded-lg"
          onClick={() => navigate("/auth")}
        >
          Start Today
        </button>
      </section>

      {/* FOOTER */}
      <footer className="text-center text-sm text-gray-500 py-8 border-t">
        © {new Date().getFullYear()} SecureVU. All rights reserved.
      </footer>

    </div>
  );
}
