import { useNavigate } from 'react-router-dom';
import { SignInPage } from "@/components/ui/sign-in";
import type { Testimonial } from "@/components/ui/sign-in";

const foodosTestimonials: Testimonial[] = [
  {
    avatarSrc: "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=150&q=80",
    name: "Sarah Chen",
    handle: "@sarah_foodos",
    text: "FoodOS reduced our kitchen prep waste by 34% in our first month across 12 locations."
  },
  {
    avatarSrc: "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=150&q=80",
    name: "Marcus Johnson",
    handle: "@marcustech",
    text: "The decision intelligence spine and RSL tracking save us thousands of rupees daily."
  },
  {
    avatarSrc: "https://images.unsplash.com/photo-1580489944761-15a19d654956?w=150&q=80",
    name: "Elena Rostova",
    handle: "@elena_ops",
    text: "Automated B2B rescue rerouting is intuitive, reliable, and keeps inventory fresh."
  },
];

// Farm gate, and all four committed locally — the sign-in screen is the first thing on
// the projector, and the H34 rehearsal runs with the wifi off.
const foodosHeroImages = [
  "/farm-field-sunrise.jpg",
  "/market-produce-crates.jpg",
  "/market-vegetables.jpg",
  "/crop-seedlings.jpg"
];

const SignInPageDemo = () => {
  const navigate = useNavigate();

  const handleSignIn = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const data: Record<string, any> = {};
    formData.forEach((value, key) => {
      data[key] = value;
    });
    console.log("FoodOS Sign In submitted:", data);
    navigate('/today');
  };

  const handleGoogleSignIn = () => {
    console.log("FoodOS Google Workspace Sign-In");
    navigate('/today');
  };
  
  const handleResetPassword = () => {
    alert("Password reset link sent to your enterprise email.");
  };

  const handleCreateAccount = () => {
    alert("Enterprise onboarding request submitted. An admin will contact your kitchen node.");
  };

  return (
    <div className="bg-slate-50 text-slate-900 min-h-screen">
      <SignInPage
        title={<span className="font-extrabold text-slate-900 tracking-tight">FoodOS Enterprise</span>}
        description="Access your AI Decision Intelligence Portal and Kitchen Waste Analytics"
        heroImageSrc={foodosHeroImages}
        testimonials={foodosTestimonials}
        onSignIn={handleSignIn}
        onGoogleSignIn={handleGoogleSignIn}
        onResetPassword={handleResetPassword}
        onCreateAccount={handleCreateAccount}
      />
    </div>
  );
};

export default SignInPageDemo;
